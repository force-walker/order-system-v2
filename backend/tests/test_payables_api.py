from datetime import UTC, date, datetime, timedelta
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.api.routes_payables import add_payment,cancel_bill,create_bill,export_bills,finalize_bill,list_bills,list_candidates,supplier_outstanding,void_payment
from app.db.base import Base
from app.models.entities import Customer,Order,OrderItem,OrderStatus,PricingBasis,Product,PurchaseResult,PurchaseResultStatus,Supplier,SupplierAllocation,PaymentTermsType
from app.schemas.payable import SupplierBillCreateRequest,SupplierPaymentCreateRequest,SupplierPaymentVoidRequest

engine=create_engine("sqlite+pysqlite:///:memory:",connect_args={"check_same_thread":False},poolclass=StaticPool)
Base.metadata.create_all(engine)

def seed(db:Session,*,supplier_name="Supplier A",cost=100):
    stamp=str(datetime.now(UTC).timestamp());s=Supplier(supplier_code=f"S-{stamp}",name=supplier_name,active=True,payment_terms_type=PaymentTermsType.half_month_15_eom)
    c=Customer(customer_code=f"C-{stamp}",name="C",active=True);p=Product(sku=f"P-{stamp}",name="Fish",order_uom="case",purchase_uom="case",invoice_uom="case",pricing_basis_default=PricingBasis.uom_count,active=True)
    db.add_all([s,c,p]);db.flush();o=Order(order_no=f"O-{stamp}",customer_id=c.id,order_datetime=datetime.now(UTC),delivery_date=date.today(),status=OrderStatus.purchased)
    db.add(o);db.flush();i=OrderItem(order_id=o.id,product_id=p.id,ordered_qty=2,pricing_basis=PricingBasis.uom_count,unit_price_uom_count=200)
    db.add(i);db.flush();a=SupplierAllocation(order_item_id=i.id,final_supplier_id=s.id,final_qty=2,final_uom="case");db.add(a);db.flush()
    pr=PurchaseResult(allocation_id=a.id,supplier_id=s.id,purchased_qty=2,purchased_uom="case",unit_cost=cost,result_status=PurchaseResultStatus.filled,recorded_at=datetime.now(UTC));db.add(pr);db.commit();return pr.id,s.id

def test_candidate_draft_due_date_claim_cancel_and_payment_lifecycle():
    with Session(engine) as db:
        pr,sid=seed(db);assert any(x.purchase_result_id==pr for x in list_candidates(db))
        b=create_bill(SupplierBillCreateRequest(purchase_result_ids=[pr],supplier_invoice_no="EXT-1",bill_date=date(2026,1,15)),db)
        assert b.bill_no.startswith("APB-") and b.due_date==date(2026,1,31) and b.subtotal==200
        assert all(x.purchase_result_id!=pr for x in list_candidates(db))
        with pytest.raises(HTTPException) as claimed:create_bill(SupplierBillCreateRequest(purchase_result_ids=[pr],supplier_invoice_no="EXT-2",bill_date=date(2026,1,15)),db)
        assert claimed.value.status_code==409
        finalized=finalize_bill(b.id,db);partial=add_payment(b.id,SupplierPaymentCreateRequest(payment_date=date(2026,1,16),amount=50,reference="BANK"),db)
        assert finalized.status.value=="finalized" and partial.payment_status=="partially_paid"
        with pytest.raises(HTTPException):add_payment(b.id,SupplierPaymentCreateRequest(payment_date=date(2026,1,16),amount=151),db)
        with pytest.raises(HTTPException):cancel_bill(b.id,db)
        payment=partial.payments[0];assert void_payment(b.id,payment.id,SupplierPaymentVoidRequest(reason="mistake"),db).payment_status=="unpaid"
        assert cancel_bill(b.id,db).status.value=="cancelled";assert any(x.purchase_result_id==pr for x in list_candidates(db))
        assert supplier_outstanding(sid,db).outstanding_amount==0

def test_mixed_supplier_duplicate_ids_history_and_exports():
    with Session(engine) as db:
        first,_=seed(db,supplier_name="A");second,_=seed(db,supplier_name="B")
        with pytest.raises(HTTPException) as mixed:create_bill(SupplierBillCreateRequest(purchase_result_ids=[first,second],supplier_invoice_no="MIX",bill_date=date.today()),db)
        assert mixed.value.status_code==422
        with pytest.raises(HTTPException):create_bill(SupplierBillCreateRequest(purchase_result_ids=[first,first],supplier_invoice_no="DUP",bill_date=date.today()),db)
        bill=create_bill(SupplierBillCreateRequest(purchase_result_ids=[first],supplier_invoice_no="SEARCH-1",bill_date=date.today()-timedelta(days=2)),db);finalize_bill(bill.id,db)
        result=list_bills(search="Fish",direction="desc",page=1,page_size=50,db=db);assert result.total>=1
        assert export_bills("headers",search="SEARCH-1",direction="desc",db=db).body.startswith(b"\xef\xbb\xbf")
