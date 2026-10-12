from datetime import UTC, date, datetime, timedelta
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.api.routes_payables import PayablePaymentStatusFilter,PayableSort,add_payment,cancel_bill,create_bill,export_bills,finalize_bill,list_bills,list_candidates,supplier_outstanding,update_bill,void_payment
from app.db.base import Base
from app.models.entities import Customer,Order,OrderItem,OrderStatus,PricingBasis,Product,PurchaseResult,PurchaseResultStatus,Supplier,SupplierAllocation,PaymentTermsType,SupplierBill,SupplierBillItem,SupplierBillStatus
from app.schemas.payable import SupplierBillCreateRequest,SupplierBillItemUpdate,SupplierBillUpdateRequest,SupplierPaymentCreateRequest,SupplierPaymentVoidRequest
from pydantic import TypeAdapter,ValidationError

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
        assert b.outstanding_amount==0 and b.payment_status is None
        assert all(x.id!=b.id for x in list_bills(payment_status="unpaid",direction="desc",page=1,page_size=50,db=db).items)
        assert all(x.purchase_result_id!=pr for x in list_candidates(db))
        with pytest.raises(HTTPException) as claimed:create_bill(SupplierBillCreateRequest(purchase_result_ids=[pr],supplier_invoice_no="EXT-2",bill_date=date(2026,1,15)),db)
        assert claimed.value.status_code==409
        finalized=finalize_bill(b.id,db);assert finalized.outstanding_amount==200 and finalized.payment_status=="unpaid"
        assert any(x.id==b.id for x in list_bills(payment_status="unpaid",direction="desc",page=1,page_size=50,db=db).items)
        partial=add_payment(b.id,SupplierPaymentCreateRequest(payment_date=date(2026,1,16),amount=50,reference="BANK"),db)
        assert partial.outstanding_amount==150 and partial.payment_status=="partially_paid"
        with pytest.raises(HTTPException):add_payment(b.id,SupplierPaymentCreateRequest(payment_date=date(2026,1,16),amount=151),db)
        with pytest.raises(HTTPException):cancel_bill(b.id,db)
        payment=partial.payments[0];assert void_payment(b.id,payment.id,SupplierPaymentVoidRequest(reason="mistake"),db).payment_status=="unpaid"
        paid=add_payment(b.id,SupplierPaymentCreateRequest(payment_date=date(2026,1,16),amount=200),db)
        assert paid.payment_status=="paid" and paid.outstanding_amount==0
        active=next(x for x in paid.payments if x.voided_at is None)
        restored=void_payment(b.id,active.id,SupplierPaymentVoidRequest(reason="reopen"),db)
        assert restored.payment_status=="unpaid" and restored.outstanding_amount==200
        cancelled=cancel_bill(b.id,db);assert cancelled.status.value=="cancelled" and cancelled.outstanding_amount==0 and cancelled.payment_status is None
        assert any(x.purchase_result_id==pr for x in list_candidates(db))
        assert supplier_outstanding(sid,db).outstanding_amount==0
        csv_row=export_bills("headers",search="EXT-1",direction="desc",db=db).body.decode("utf-8-sig").splitlines()[1].split(",")
        assert csv_row[6]=="" and float(csv_row[13])==0

def test_mixed_supplier_duplicate_ids_history_and_exports():
    with Session(engine) as db:
        first,_=seed(db,supplier_name="A");second,_=seed(db,supplier_name="B")
        with pytest.raises(HTTPException) as mixed:create_bill(SupplierBillCreateRequest(purchase_result_ids=[first,second],supplier_invoice_no="MIX",bill_date=date.today()),db)
        assert mixed.value.status_code==422
        with pytest.raises(HTTPException):create_bill(SupplierBillCreateRequest(purchase_result_ids=[first,first],supplier_invoice_no="DUP",bill_date=date.today()),db)
        bill=create_bill(SupplierBillCreateRequest(purchase_result_ids=[first],supplier_invoice_no="SEARCH-1",bill_date=date.today()-timedelta(days=2)),db);finalize_bill(bill.id,db)
        result=list_bills(search="Fish",direction="desc",page=1,page_size=50,db=db);assert result.total>=1
        assert export_bills("headers",search="SEARCH-1",direction="desc",db=db).body.startswith(b"\xef\xbb\xbf")

def test_missing_cost_remains_null_until_draft_edit_and_zero_is_valid():
    with Session(engine) as db:
        missing,_=seed(db,cost=None);candidate=next(x for x in list_candidates(db) if x.purchase_result_id==missing);assert candidate.unit_cost is None and candidate.amount is None
        bill=create_bill(SupplierBillCreateRequest(purchase_result_ids=[missing],supplier_invoice_no=" NO-COST ",bill_date=date.today()),db)
        assert bill.supplier_invoice_no=="NO-COST" and bill.items[0].unit_cost is None and bill.items[0].line_amount is None
        with pytest.raises(HTTPException) as blocked:finalize_bill(bill.id,db)
        assert blocked.value.status_code==422
        edited=update_bill(bill.id,SupplierBillUpdateRequest(items={bill.items[0].id:SupplierBillItemUpdate(quantity=2,unit_cost=0)}),db)
        assert edited.items[0].unit_cost==0 and edited.items[0].line_amount==0
        finalized=finalize_bill(bill.id,db)
        assert finalized.status==SupplierBillStatus.finalized and finalized.total_amount==0
        assert finalized.outstanding_amount==0 and finalized.payment_status=="paid"
        paid=list_bills(payment_status="paid",direction="desc",page=1,page_size=50,db=db)
        assert any(x.id==bill.id and x.payment_status=="paid" and x.outstanding_amount==0 for x in paid.items)
        csv_row=export_bills("headers",search="NO-COST",direction="desc",db=db).body.decode("utf-8-sig").splitlines()[1].split(",")
        assert csv_row[6]=="paid" and float(csv_row[13])==0

def test_currency_invoice_number_and_patch_null_validation():
    with pytest.raises(ValidationError):SupplierBillCreateRequest(purchase_result_ids=[1],supplier_invoice_no="X",bill_date=date.today(),currency="USD")
    with pytest.raises(ValidationError):SupplierBillCreateRequest(purchase_result_ids=[1],supplier_invoice_no="   ",bill_date=date.today())
    for field in ({"bill_date":None},{"supplier_invoice_no":None},{"tax":None}):
        with pytest.raises(ValidationError):SupplierBillUpdateRequest(**field)
    with Session(engine) as db:
        first,supplier_id=seed(db);second,_=seed(db);db.get(PurchaseResult,second).supplier_id=supplier_id;db.commit()
        one=create_bill(SupplierBillCreateRequest(purchase_result_ids=[first],supplier_invoice_no="EXT-NORM",bill_date=date.today()),db)
        with pytest.raises(HTTPException) as duplicate:create_bill(SupplierBillCreateRequest(purchase_result_ids=[second],supplier_invoice_no=" EXT-NORM ",bill_date=date.today()),db)
        assert duplicate.value.status_code==409 and one.supplier_invoice_no=="EXT-NORM"

def test_database_pagination_and_csv_are_not_truncated_at_200():
    with Session(engine) as db:
        supplier=Supplier(supplier_code=f"PAG-{datetime.now(UTC).timestamp()}",name="Pagination Supplier",active=True);db.add(supplier);db.flush()
        for index in range(205):
            bill=SupplierBill(document_seq=100000+index,next_line_no=20,bill_no=f"APB-T{index:06d}",supplier_id=supplier.id,supplier_invoice_no=f"EXT-T{index:06d}",bill_date=date.today(),currency="JPY",status=SupplierBillStatus.finalized,subtotal=1,tax=0,adjustment=0,total_amount=1)
            db.add(bill);db.flush();db.add(SupplierBillItem(supplier_bill_id=bill.id,line_no=10,purchase_result_id=900000+index,product_id=900000+index,sku=f"SKU-T{index}",description="Pagination Product",quantity=1,uom="piece",unit_cost=1,line_amount=1))
        # Disable FK checks only for this isolated SQLite pagination fixture; production keeps real FKs.
        db.commit()
        first=list_bills(search="Pagination",direction="desc",page=1,page_size=50,db=db);last=list_bills(search="Pagination",direction="desc",page=5,page_size=50,db=db)
        assert first.total==205 and len(first.items)==50 and len(last.items)==5
        header=export_bills("headers",search="Pagination",direction="desc",db=db).body.decode("utf-8-sig").splitlines()
        line=export_bills("lines",search="Pagination",direction="desc",db=db).body.decode("utf-8-sig").splitlines()
        assert len(header)==206 and len(line)==206

def test_payable_filter_types_reject_invalid_values_before_route_execution():
    for filter_type in (SupplierBillStatus,PayablePaymentStatusFilter,PayableSort):
        with pytest.raises(ValidationError):TypeAdapter(filter_type).validate_python("invalid")
