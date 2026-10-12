"""PostgreSQL-only Supplier Bill trigger and concurrency coverage."""
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC,date,datetime
import os
from threading import Barrier
from uuid import uuid4
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine,text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.api.routes_payables import add_payment,cancel_bill,create_bill,finalize_bill
from app.core.exception_mapping import map_integrity_error
from app.core.numbering import ensure_order_header_numbers,ensure_order_item_number
from app.models.entities import Customer,LineStatus,Order,OrderItem,OrderStatus,PricingBasis,Product,PurchaseResult,PurchaseResultStatus,Supplier,SupplierAllocation
from app.schemas.payable import SupplierBillCreateRequest,SupplierPaymentCreateRequest

def _engine():
    url=os.getenv('TEST_POSTGRES_URL')
    if not url:pytest.skip('TEST_POSTGRES_URL required for PostgreSQL payable regression')
    engine=create_engine(url);assert engine.dialect.name=='postgresql';return engine

def test_supplier_bill_claim_invoice_number_cancel_reuse_and_payment_concurrency():
    engine=_engine();marker='AP-'+uuid4().hex[:12];ids={}
    try:
        with Session(engine) as db:
            customer=Customer(customer_code=marker,name=marker,active=True);supplier=Supplier(supplier_code=marker,name=marker,active=True)
            product=Product(sku=marker,name=marker,order_uom='piece',purchase_uom='piece',invoice_uom='piece',pricing_basis_default=PricingBasis.uom_count,active=True)
            db.add_all([customer,supplier,product]);db.flush();order=Order(order_no='pending-'+marker,customer_id=customer.id,order_datetime=datetime.now(UTC),delivery_date=date.today(),status=OrderStatus.purchased)
            ensure_order_header_numbers(db,order);db.add(order);db.flush()
            items=[];allocations=[];results=[]
            for _ in range(2):
                item=OrderItem(order_id=order.id,product_id=product.id,ordered_qty=1,pricing_basis=PricingBasis.uom_count,unit_price_uom_count=1,line_status=LineStatus.purchased)
                ensure_order_item_number(db,order,item);db.add(item);db.flush();items.append(item.id)
                allocation=SupplierAllocation(order_item_id=item.id,final_supplier_id=supplier.id,final_qty=1,final_uom='piece');db.add(allocation);db.flush();allocations.append(allocation.id)
                result=PurchaseResult(allocation_id=allocation.id,supplier_id=supplier.id,purchased_qty=1,purchased_uom='piece',unit_cost=100,result_status=PurchaseResultStatus.filled);db.add(result);db.flush();results.append(result.id)
            db.commit()
            ids.update(customer=customer.id,supplier=supplier.id,product=product.id,order=order.id,items=items,allocations=allocations,results=results)
        barrier=Barrier(2)
        def claim(invoice_no):
            with Session(engine) as db:
                barrier.wait(timeout=10)
                try:return ('ok',create_bill(SupplierBillCreateRequest(purchase_result_ids=[ids['results'][0]],supplier_invoice_no=invoice_no,bill_date=date.today()),db).id)
                except HTTPException as exc:db.rollback();return ('error',exc.status_code,exc.detail['code'])
                except IntegrityError as exc:
                    db.rollback();status,code,_=map_integrity_error(exc);return ('error',status,code)
        outcomes=list(ThreadPoolExecutor(max_workers=2).map(claim,['EXT-CONCURRENT','EXT-CONCURRENT-2']))
        assert [x[0] for x in outcomes].count('ok')==1
        assert next(x[1:] for x in outcomes if x[0]=='error')==(409,'PURCHASE_RESULT_ALREADY_CLAIMED')
        bill_id=next(x[1] for x in outcomes if x[0]=='ok')
        with Session(engine) as db:
            assert cancel_bill(bill_id,db).status.value=='cancelled'

        invoice_barrier=Barrier(2)
        def duplicate_invoice(result_id):
            with Session(engine) as db:
                invoice_barrier.wait(timeout=10)
                try:return ('ok',create_bill(SupplierBillCreateRequest(purchase_result_ids=[result_id],supplier_invoice_no='EXT-SAME',bill_date=date.today()),db).id)
                except HTTPException as exc:db.rollback();return ('error',exc.status_code,exc.detail['code'])
                except IntegrityError as exc:
                    db.rollback();status,code,_=map_integrity_error(exc);return ('error',status,code)
        duplicate_outcomes=list(ThreadPoolExecutor(max_workers=2).map(duplicate_invoice,ids['results']))
        assert [x[0] for x in duplicate_outcomes].count('ok')==1
        assert next(x[1:] for x in duplicate_outcomes if x[0]=='error')==(409,'SUPPLIER_INVOICE_NO_EXISTS')
        duplicate_bill_id=next(x[1] for x in duplicate_outcomes if x[0]=='ok')
        with Session(engine) as db:
            assert cancel_bill(duplicate_bill_id,db).status.value=='cancelled'
            reused=create_bill(SupplierBillCreateRequest(purchase_result_ids=[ids['results'][0]],supplier_invoice_no='EXT-SAME',bill_date=date.today()),db)
            finalized=finalize_bill(reused.id,db);assert finalized.status.value=='finalized';ids['bill']=reused.id
        pay_barrier=Barrier(2)
        def pay():
            with Session(engine) as db:
                pay_barrier.wait(timeout=10)
                try:add_payment(ids['bill'],SupplierPaymentCreateRequest(payment_date=date.today(),amount=60),db);return 'ok'
                except HTTPException as exc:db.rollback();return exc.detail['code']
        payments=list(ThreadPoolExecutor(max_workers=2).map(lambda _:pay(),range(2)))
        assert payments.count('ok')==1 and 'PAYMENT_EXCEEDS_OUTSTANDING' in payments
    finally:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM supplier_payments WHERE supplier_bill_id IN (SELECT id FROM supplier_bills WHERE supplier_id=:supplier)"),ids)
            conn.execute(text("DELETE FROM supplier_bill_items WHERE supplier_bill_id IN (SELECT id FROM supplier_bills WHERE supplier_id=:supplier)"),ids)
            conn.execute(text("DELETE FROM supplier_bills WHERE supplier_id=:supplier"),ids)
            conn.execute(text("DELETE FROM purchase_results WHERE id = ANY(:results)"),ids);conn.execute(text("DELETE FROM supplier_allocations WHERE id = ANY(:allocations)"),ids)
            conn.execute(text("DELETE FROM order_items WHERE id = ANY(:items)"),ids);conn.execute(text("DELETE FROM orders WHERE id=:order"),ids)
            conn.execute(text("DELETE FROM products WHERE id=:product"),ids);conn.execute(text("DELETE FROM customers WHERE id=:customer"),ids);conn.execute(text("DELETE FROM suppliers WHERE id=:supplier"),ids)
        engine.dispose()
