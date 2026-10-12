import csv
import io
from datetime import UTC, date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import and_, asc, case, desc, func, or_, select
from sqlalchemy.orm import Session

from app.core.business_time import hong_kong_today
from app.core.numbering import ensure_supplier_bill_numbers
from app.core.payment_terms import calculate_due_date
from app.db.session import get_db
from app.models.entities import (Order, OrderItem, Product, PurchaseResult, Supplier, SupplierAllocation,
    SupplierBill, SupplierBillItem, SupplierBillStatus, SupplierPayment)
from app.schemas.payable import (PayableCandidate, SupplierBillCreateRequest, SupplierBillListResponse,
    SupplierBillNeighborsResponse, SupplierBillResponse, SupplierBillUpdateRequest,
    SupplierOutstandingResponse, SupplierPaymentCreateRequest, SupplierPaymentVoidRequest)

router = APIRouter(prefix="/api/v1/payables", tags=["accounts-payable"])
MONEY = Decimal("0.01")
PayablePaymentStatusFilter = Literal["unpaid", "partially_paid", "paid"]
PayableSort = Literal["document_seq", "bill_date", "due_date", "bill_no", "supplier_invoice_no", "supplier", "status", "total"]

def _money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(MONEY, rounding=ROUND_HALF_UP)

def _payment_values(db: Session, bill: SupplierBill):
    paid = sum((_money(x.amount) for x in db.query(SupplierPayment).filter(
        SupplierPayment.supplier_bill_id == bill.id, SupplierPayment.voided_at.is_(None)).all()), Decimal("0"))
    total = _money(bill.total_amount)
    if bill.status != SupplierBillStatus.finalized:
        return paid, Decimal("0"), None, False
    outstanding = max(total - paid, Decimal("0"))
    status = "paid" if outstanding <= 0 else ("unpaid" if paid <= 0 else "partially_paid")
    overdue = bill.status == SupplierBillStatus.finalized and outstanding > 0 and bill.due_date is not None and bill.due_date < hong_kong_today()
    return paid, outstanding, status, overdue

def _response(db: Session, bill: SupplierBill, *, include_detail: bool = True) -> SupplierBillResponse:
    supplier = db.get(Supplier, bill.supplier_id)
    items = db.query(SupplierBillItem).filter(SupplierBillItem.supplier_bill_id == bill.id).order_by(SupplierBillItem.line_no).all()
    payments = db.query(SupplierPayment).filter(SupplierPayment.supplier_bill_id == bill.id).order_by(SupplierPayment.payment_date, SupplierPayment.created_at).all()
    paid, outstanding, payment_status, overdue = _payment_values(db, bill)
    return SupplierBillResponse(
        id=bill.id, document_seq=bill.document_seq, bill_no=bill.bill_no, supplier_id=bill.supplier_id,
        supplier_name=supplier.name if supplier else "", supplier_invoice_no=bill.supplier_invoice_no,
        bill_date=bill.bill_date, due_date=bill.due_date, payment_terms_type=bill.payment_terms_type,
        payment_terms_days=bill.payment_terms_days, currency=bill.currency, status=bill.status,
        subtotal=float(bill.subtotal), tax=float(bill.tax), adjustment=float(bill.adjustment), total_amount=float(bill.total_amount),
        paid_amount=float(paid), outstanding_amount=float(outstanding), payment_status=payment_status, overdue=overdue,
        line_count=len(items),
        items=[dict(id=x.id, line_no=x.line_no, purchase_result_id=x.purchase_result_id, product_id=x.product_id,
            sku=x.sku, description=x.description, quantity=float(x.quantity), uom=x.uom,
            unit_cost=float(x.unit_cost) if x.unit_cost is not None else None,
            line_amount=float(x.line_amount) if x.line_amount is not None else None) for x in items] if include_detail else [],
        payments=[dict(id=x.id, payment_date=x.payment_date, amount=float(x.amount), reference=x.reference,
            note=x.note, created_at=x.created_at, voided_at=x.voided_at, void_reason=x.void_reason) for x in payments] if include_detail else [],
    )

def _recalculate(db: Session, bill: SupplierBill) -> None:
    subtotal = sum((_money(x.line_amount) for x in db.query(SupplierBillItem).filter(
        SupplierBillItem.supplier_bill_id == bill.id, SupplierBillItem.line_amount.is_not(None))), Decimal("0"))
    bill.subtotal = subtotal
    bill.total_amount = _money(subtotal + _money(bill.tax) + _money(bill.adjustment))

def _active_claim_exists():
    return select(SupplierBillItem.id).join(SupplierBill, SupplierBill.id == SupplierBillItem.supplier_bill_id).where(
        SupplierBillItem.purchase_result_id == PurchaseResult.id, SupplierBill.status != SupplierBillStatus.cancelled).exists()

def _candidate_query(db: Session):
    return (db.query(PurchaseResult, Supplier, Product, Order, OrderItem)
        .join(SupplierAllocation, SupplierAllocation.id == PurchaseResult.allocation_id)
        .join(OrderItem, OrderItem.id == SupplierAllocation.order_item_id)
        .join(Order, Order.id == OrderItem.order_id).join(Product, Product.id == OrderItem.product_id)
        .join(Supplier, Supplier.id == PurchaseResult.supplier_id)
        .filter(~_active_claim_exists()))

@router.get("/candidates", response_model=list[PayableCandidate])
def list_candidates(db: Session = Depends(get_db)):
    rows = _candidate_query(db).order_by(PurchaseResult.recorded_at.desc(), Order.document_seq.desc(), OrderItem.line_no.asc()).all()
    result = []
    for pr, supplier, product, order, item in rows:
        cost = pr.final_unit_cost if pr.final_unit_cost is not None else pr.unit_cost
        result.append(PayableCandidate(purchase_result_id=pr.id, purchase_date=pr.recorded_at.date(), supplier_id=supplier.id,
            supplier_name=supplier.name, order_no=order.order_no, line_no=item.line_no, product_id=product.id,
            sku=product.sku, product_name=product.name, quantity=float(pr.purchased_qty), uom=pr.purchased_uom,
            unit_cost=float(cost) if cost is not None else None,
            amount=float(_money(Decimal(str(pr.purchased_qty)) * Decimal(str(cost)))) if cost is not None else None))
    return result

@router.post("/bills", response_model=SupplierBillResponse, status_code=201)
def create_bill(payload: SupplierBillCreateRequest, db: Session = Depends(get_db)):
    ids = list(dict.fromkeys(payload.purchase_result_ids))
    if len(ids) != len(payload.purchase_result_ids):
        raise HTTPException(422, detail={"code":"DUPLICATE_PURCHASE_RESULT_ID","message":"purchase_result_ids must be unique"})
    rows = (_candidate_query(db).filter(PurchaseResult.id.in_(ids)).with_for_update().all())
    if len(rows) != len(ids):
        raise HTTPException(409, detail={"code":"PURCHASE_RESULT_ALREADY_CLAIMED","message":"one or more purchase results are unavailable"})
    supplier_ids = {row[1].id for row in rows}
    if len(supplier_ids) != 1:
        raise HTTPException(422, detail={"code":"MIXED_SUPPLIERS","message":"all purchase results must belong to the same supplier"})
    supplier = rows[0][1]
    supplier_invoice_no = payload.supplier_invoice_no.strip()
    duplicate = db.query(SupplierBill.id).filter(SupplierBill.supplier_id == supplier.id,
        SupplierBill.supplier_invoice_no == supplier_invoice_no, SupplierBill.status != SupplierBillStatus.cancelled).first()
    if duplicate:
        raise HTTPException(409, detail={"code":"SUPPLIER_INVOICE_NO_EXISTS","message":"supplier invoice number already exists for this supplier"})
    bill = SupplierBill(document_seq=None, bill_no=f"pending-{datetime.now(UTC).timestamp()}", supplier_id=supplier.id,
        supplier_invoice_no=supplier_invoice_no, bill_date=payload.bill_date,
        due_date=calculate_due_date(payload.bill_date, supplier.payment_terms_type, supplier.payment_terms_days),
        payment_terms_type=supplier.payment_terms_type, payment_terms_days=supplier.payment_terms_days,
        currency=payload.currency.upper(), status=SupplierBillStatus.draft, subtotal=0, tax=0, adjustment=0, total_amount=0)
    db.add(bill); ensure_supplier_bill_numbers(db, bill); db.flush()
    by_id = {row[0].id: row for row in rows}
    for index, pr_id in enumerate(ids, 1):
        pr, _, product, _, _ = by_id[pr_id]
        cost = pr.final_unit_cost if pr.final_unit_cost is not None else pr.unit_cost
        unit_cost = _money(cost) if cost is not None else None
        qty = Decimal(str(pr.purchased_qty))
        db.add(SupplierBillItem(supplier_bill_id=bill.id, line_no=index * 10, purchase_result_id=pr.id,
            product_id=product.id, sku=product.sku, description=product.name, quantity=qty, uom=pr.purchased_uom,
            unit_cost=unit_cost, line_amount=_money(qty * unit_cost) if unit_cost is not None else None))
    db.flush(); _recalculate(db, bill); db.commit(); db.refresh(bill)
    return _response(db, bill)

def _get_bill(db: Session, bill_id: str, *, lock=False):
    q = db.query(SupplierBill).filter(SupplierBill.id == bill_id)
    bill = q.with_for_update().first() if lock else q.first()
    if bill is None: raise HTTPException(404, detail={"code":"SUPPLIER_BILL_NOT_FOUND","message":"supplier bill not found"})
    return bill

@router.get("/bills/{bill_id}", response_model=SupplierBillResponse)
def get_bill(bill_id: str, db: Session = Depends(get_db)): return _response(db, _get_bill(db, bill_id))

@router.patch("/bills/{bill_id}", response_model=SupplierBillResponse)
def update_bill(bill_id: str, payload: SupplierBillUpdateRequest, db: Session = Depends(get_db)):
    bill = _get_bill(db, bill_id, lock=True)
    if bill.status != SupplierBillStatus.draft: raise HTTPException(409, detail={"code":"SUPPLIER_BILL_LOCKED","message":"only draft bills are editable"})
    data = payload.model_dump(exclude_unset=True); data.pop("items", None); item_changes = payload.items
    if "supplier_invoice_no" in data:
        normalized = data["supplier_invoice_no"].strip()
        duplicate = db.query(SupplierBill.id).filter(SupplierBill.id != bill.id,
            SupplierBill.supplier_id == bill.supplier_id, SupplierBill.supplier_invoice_no == normalized,
            SupplierBill.status != SupplierBillStatus.cancelled).first()
        if duplicate:
            raise HTTPException(409, detail={"code":"SUPPLIER_INVOICE_NO_EXISTS","message":"supplier invoice number already exists for this supplier"})
        data["supplier_invoice_no"] = normalized
    for key, value in data.items(): setattr(bill, key, value)
    if "bill_date" in data:
        bill.due_date = calculate_due_date(bill.bill_date, bill.payment_terms_type, bill.payment_terms_days)
    if item_changes:
        items = {x.id: x for x in db.query(SupplierBillItem).filter(SupplierBillItem.supplier_bill_id == bill.id)}
        for item_id, change in item_changes.items():
            if item_id not in items: raise HTTPException(422, detail={"code":"BILL_ITEM_NOT_FOUND","message":"bill item does not belong to bill"})
            item = items[item_id]; item.quantity=change.quantity; item.unit_cost=change.unit_cost
            item.line_amount=(_money(Decimal(str(change.quantity))*Decimal(str(change.unit_cost)))
                if change.unit_cost is not None else None)
    _recalculate(db, bill); db.commit(); db.refresh(bill); return _response(db, bill)

@router.post("/bills/{bill_id}/finalize", response_model=SupplierBillResponse)
def finalize_bill(bill_id: str, db: Session = Depends(get_db)):
    bill=_get_bill(db,bill_id,lock=True)
    if bill.status != SupplierBillStatus.draft: raise HTTPException(409, detail={"code":"SUPPLIER_BILL_NOT_DRAFT","message":"only draft bills can be finalized"})
    items=db.query(SupplierBillItem).filter(SupplierBillItem.supplier_bill_id==bill.id).all()
    if not items or any(x.unit_cost is None or Decimal(str(x.quantity))<=0 or Decimal(str(x.unit_cost))<0 for x in items):
        raise HTTPException(422, detail={"code":"SUPPLIER_BILL_INVALID_LINES","message":"quantity and unit cost are required"})
    bill.status=SupplierBillStatus.finalized; db.commit(); db.refresh(bill); return _response(db,bill)

@router.post("/bills/{bill_id}/cancel", response_model=SupplierBillResponse)
def cancel_bill(bill_id: str, db: Session = Depends(get_db)):
    bill=_get_bill(db,bill_id,lock=True); paid,_,_,_=_payment_values(db,bill)
    if paid > 0: raise HTTPException(409, detail={"code":"SUPPLIER_BILL_HAS_PAYMENTS","message":"bill with active payments cannot be cancelled"})
    if bill.status == SupplierBillStatus.cancelled: return _response(db,bill)
    bill.status=SupplierBillStatus.cancelled; db.commit(); db.refresh(bill); return _response(db,bill)

@router.post("/bills/{bill_id}/payments", response_model=SupplierBillResponse, status_code=201)
def add_payment(bill_id: str, payload: SupplierPaymentCreateRequest, db: Session = Depends(get_db)):
    bill=_get_bill(db,bill_id,lock=True)
    if bill.status != SupplierBillStatus.finalized: raise HTTPException(409, detail={"code":"SUPPLIER_BILL_NOT_FINALIZED","message":"payments require a finalized bill"})
    _, outstanding,_,_=_payment_values(db,bill)
    if _money(payload.amount)>outstanding: raise HTTPException(422, detail={"code":"PAYMENT_EXCEEDS_OUTSTANDING","message":"payment exceeds outstanding amount"})
    db.add(SupplierPayment(supplier_bill_id=bill.id, payment_date=payload.payment_date, amount=_money(payload.amount), reference=payload.reference, note=payload.note))
    db.commit(); db.refresh(bill); return _response(db,bill)

@router.post("/bills/{bill_id}/payments/{payment_id}/void", response_model=SupplierBillResponse)
def void_payment(bill_id: str, payment_id: str, payload: SupplierPaymentVoidRequest, db: Session = Depends(get_db)):
    bill=_get_bill(db,bill_id,lock=True); payment=db.query(SupplierPayment).filter(SupplierPayment.id==payment_id,SupplierPayment.supplier_bill_id==bill.id).first()
    if payment is None: raise HTTPException(404, detail={"code":"SUPPLIER_PAYMENT_NOT_FOUND","message":"payment not found"})
    if payment.voided_at is not None: raise HTTPException(409, detail={"code":"SUPPLIER_PAYMENT_ALREADY_VOIDED","message":"payment is already voided"})
    payment.voided_at=datetime.now(UTC); payment.void_reason=payload.reason; db.commit(); db.refresh(bill); return _response(db,bill)

def _history_query(db: Session, search=None, date_from=None, date_to=None, supplier_id=None, bill_status=None, payment_status=None, overdue=None):
    payment_totals = (select(SupplierPayment.supplier_bill_id,
        func.coalesce(func.sum(case((SupplierPayment.voided_at.is_(None), SupplierPayment.amount), else_=0)), 0).label("paid_amount"))
        .group_by(SupplierPayment.supplier_bill_id).subquery())
    line_counts = (select(SupplierBillItem.supplier_bill_id, func.count(SupplierBillItem.id).label("line_count"))
        .group_by(SupplierBillItem.supplier_bill_id).subquery())
    paid = func.coalesce(payment_totals.c.paid_amount, 0)
    outstanding = case((and_(SupplierBill.status == SupplierBillStatus.finalized,
        SupplierBill.total_amount - paid > 0), SupplierBill.total_amount - paid), else_=0)
    finalized_payment_state = case((outstanding <= 0, "paid"), (paid <= 0, "unpaid"), else_="partially_paid")
    payment_state = case((SupplierBill.status == SupplierBillStatus.finalized, finalized_payment_state), else_=None)
    overdue_state = and_(SupplierBill.status == SupplierBillStatus.finalized, outstanding > 0,
        SupplierBill.due_date.is_not(None), SupplierBill.due_date < hong_kong_today())
    q=(db.query(SupplierBill, Supplier, func.coalesce(line_counts.c.line_count, 0), paid, outstanding,
        payment_state, overdue_state)
        .join(Supplier,Supplier.id==SupplierBill.supplier_id)
        .outerjoin(payment_totals,payment_totals.c.supplier_bill_id==SupplierBill.id)
        .outerjoin(line_counts,line_counts.c.supplier_bill_id==SupplierBill.id))
    if search:
        p=f"%{search.strip()}%"; line_match=select(SupplierBillItem.id).where(SupplierBillItem.supplier_bill_id==SupplierBill.id,
            or_(SupplierBillItem.sku.ilike(p),SupplierBillItem.description.ilike(p))).exists()
        q=q.filter(or_(SupplierBill.bill_no.ilike(p),SupplierBill.supplier_invoice_no.ilike(p),Supplier.name.ilike(p),line_match))
    if date_from:q=q.filter(SupplierBill.bill_date>=date_from)
    if date_to:q=q.filter(SupplierBill.bill_date<=date_to)
    if supplier_id:q=q.filter(SupplierBill.supplier_id==supplier_id)
    if bill_status:q=q.filter(SupplierBill.status==bill_status)
    if payment_status:q=q.filter(payment_state==payment_status)
    if overdue is not None:q=q.filter(overdue_state if overdue else ~overdue_state)
    return q

def _ordering(sort,direction):
    fn=asc if direction=="asc" else desc; cols={"bill_date":SupplierBill.bill_date,"due_date":SupplierBill.due_date,"bill_no":SupplierBill.bill_no,"supplier_invoice_no":SupplierBill.supplier_invoice_no,"supplier":Supplier.name,"status":SupplierBill.status,"total":SupplierBill.total_amount}
    return fn(cols.get(sort,SupplierBill.document_seq)),fn(SupplierBill.document_seq),fn(SupplierBill.id)

def _summary(row) -> SupplierBillResponse:
    bill,supplier,line_count,paid,outstanding,payment_status,overdue=row
    return SupplierBillResponse(id=bill.id,document_seq=bill.document_seq,bill_no=bill.bill_no,supplier_id=bill.supplier_id,
        supplier_name=supplier.name,supplier_invoice_no=bill.supplier_invoice_no,bill_date=bill.bill_date,due_date=bill.due_date,
        payment_terms_type=bill.payment_terms_type,payment_terms_days=bill.payment_terms_days,currency=bill.currency,status=bill.status,
        subtotal=float(bill.subtotal),tax=float(bill.tax),adjustment=float(bill.adjustment),total_amount=float(bill.total_amount),
        paid_amount=float(paid),outstanding_amount=float(outstanding),payment_status=payment_status,overdue=bool(overdue),line_count=int(line_count))

@router.get("/bills", response_model=SupplierBillListResponse)
def list_bills(search: str|None=None,date_from:date|None=None,date_to:date|None=None,supplier_id:int|None=None,bill_status:SupplierBillStatus|None=None,
    payment_status:PayablePaymentStatusFilter|None=None,overdue:bool|None=None,
    sort:PayableSort="document_seq",
    direction:Literal["asc","desc"]="desc",page:int=Query(1,ge=1),page_size:int=Query(50,ge=1,le=200),db:Session=Depends(get_db)):
    q=_history_query(db,search,date_from,date_to,supplier_id,bill_status,payment_status,overdue)
    total=q.count(); rows=q.order_by(*_ordering(sort,direction)).offset((page-1)*page_size).limit(page_size).all()
    return SupplierBillListResponse(items=[_summary(row) for row in rows],total=total,page=page,page_size=page_size)

@router.get("/bills/export/{kind}")
def export_bills(kind:str, search:str|None=None,date_from:date|None=None,date_to:date|None=None,supplier_id:int|None=None,bill_status:SupplierBillStatus|None=None,
    payment_status:PayablePaymentStatusFilter|None=None,overdue:bool|None=None,
    sort:PayableSort="document_seq",
    direction:Literal["asc","desc"]="desc",db:Session=Depends(get_db)):
    if kind not in {"headers","lines"}: raise HTTPException(404,detail={"code":"EXPORT_NOT_FOUND","message":"unknown export type"})
    rows=_history_query(db,search,date_from,date_to,supplier_id,bill_status,payment_status,overdue).order_by(*_ordering(sort,direction)).all()
    summaries=[_summary(row) for row in rows]
    out=io.StringIO(); w=csv.writer(out)
    if kind=="headers":
        w.writerow(["bill_no","supplier_invoice_no","supplier","bill_date","due_date","status","payment_status","currency","subtotal","tax","adjustment","total","paid","outstanding","overdue"])
        for x in summaries:w.writerow([x.bill_no,x.supplier_invoice_no,x.supplier_name,x.bill_date,x.due_date or "",x.status.value,x.payment_status,x.currency,x.subtotal,x.tax,x.adjustment,x.total_amount,x.paid_amount,x.outstanding_amount,str(x.overdue).lower()])
    else:
        w.writerow(["bill_no","supplier_invoice_no","supplier","bill_date","line_no","sku","product","quantity","uom","unit_cost","line_amount"])
        bill_ids=[x.id for x in summaries]
        details=(db.query(SupplierBill,Supplier,SupplierBillItem).join(Supplier,Supplier.id==SupplierBill.supplier_id)
            .join(SupplierBillItem,SupplierBillItem.supplier_bill_id==SupplierBill.id).filter(SupplierBill.id.in_(bill_ids))
            .order_by(*_ordering(sort,direction),SupplierBillItem.line_no.asc()).all()) if bill_ids else []
        for bill,supplier,x in details:w.writerow([bill.bill_no,bill.supplier_invoice_no,supplier.name,bill.bill_date,x.line_no,x.sku,x.description,x.quantity,x.uom,x.unit_cost if x.unit_cost is not None else "",x.line_amount if x.line_amount is not None else ""])
    return Response(content="\ufeff"+out.getvalue(),media_type="text/csv; charset=utf-8",headers={"Content-Disposition":f'attachment; filename="accounts-payable-{kind}.csv"'})

@router.get("/bills/{bill_id}/neighbors",response_model=SupplierBillNeighborsResponse)
def neighbors(bill_id:str,search:str|None=None,date_from:date|None=None,date_to:date|None=None,supplier_id:int|None=None,bill_status:SupplierBillStatus|None=None,
    payment_status:PayablePaymentStatusFilter|None=None,overdue:bool|None=None,
    sort:PayableSort="document_seq",
    direction:Literal["asc","desc"]="desc",db:Session=Depends(get_db)):
    rows=_history_query(db,search,date_from,date_to,supplier_id,bill_status,payment_status,overdue).order_by(*_ordering(sort,direction)).all()
    ids=[x[0].id for x in rows]
    if bill_id not in ids: raise HTTPException(404,detail={"code":"SUPPLIER_BILL_NOT_FOUND","message":"supplier bill not found"})
    i=ids.index(bill_id); return SupplierBillNeighborsResponse(previous_id=ids[i-1] if i>0 else None,next_id=ids[i+1] if i+1<len(ids) else None)

@router.get("/suppliers/{supplier_id}/outstanding",response_model=SupplierOutstandingResponse)
def supplier_outstanding(supplier_id:int,db:Session=Depends(get_db)):
    payment_totals=(select(SupplierPayment.supplier_bill_id,func.coalesce(func.sum(case((SupplierPayment.voided_at.is_(None),SupplierPayment.amount),else_=0)),0).label("paid"))
        .group_by(SupplierPayment.supplier_bill_id).subquery())
    paid=func.coalesce(payment_totals.c.paid,0)
    outstanding=case((SupplierBill.total_amount-paid>0,SupplierBill.total_amount-paid),else_=0)
    amount=(db.query(func.coalesce(func.sum(outstanding),0)).outerjoin(payment_totals,payment_totals.c.supplier_bill_id==SupplierBill.id)
        .filter(SupplierBill.supplier_id==supplier_id,SupplierBill.status==SupplierBillStatus.finalized).scalar())
    return SupplierOutstandingResponse(supplier_id=supplier_id,outstanding_amount=float(amount or 0))
