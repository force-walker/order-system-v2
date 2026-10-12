from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import (
    Delivery,
    Invoice,
    InvoiceItem,
    Order,
    OrderItem,
    PurchaseResult,
    SupplierAllocation,
    SupplierBill,
    SupplierBillItem,
)
from app.schemas.related_document import RelatedDocument, RelatedDocumentsResponse


router = APIRouter(prefix="/api/v1/related-documents", tags=["related-documents"])
DocumentType = Literal["order", "delivery", "invoice", "supplier_bill"]


def _not_found(document_type: str) -> HTTPException:
    return HTTPException(404, detail={"code": "DOCUMENT_NOT_FOUND", "message": f"{document_type} not found"})


def _order_ids_for_document(db: Session, document_type: DocumentType, document_id: str) -> set[str]:
    if document_type == "order":
        if db.get(Order, document_id) is None:
            raise _not_found(document_type)
        return {document_id}
    if document_type == "delivery":
        delivery = db.get(Delivery, document_id)
        if delivery is None:
            raise _not_found(document_type)
        return {delivery.order_id}
    if document_type == "invoice":
        invoice = db.get(Invoice, document_id)
        if invoice is None:
            raise _not_found(document_type)
        rows = (
            db.query(OrderItem.order_id)
            .join(InvoiceItem, InvoiceItem.order_item_id == OrderItem.id)
            .filter(InvoiceItem.invoice_id == invoice.id)
            .distinct()
            .all()
        )
        order_ids = {row[0] for row in rows}
        if invoice.delivery_id:
            delivery = db.get(Delivery, invoice.delivery_id)
            if delivery:
                order_ids.add(delivery.order_id)
        return order_ids
    bill = db.get(SupplierBill, document_id)
    if bill is None:
        raise _not_found(document_type)
    rows = (
        db.query(OrderItem.order_id)
        .join(SupplierAllocation, SupplierAllocation.order_item_id == OrderItem.id)
        .join(PurchaseResult, PurchaseResult.allocation_id == SupplierAllocation.id)
        .join(SupplierBillItem, SupplierBillItem.purchase_result_id == PurchaseResult.id)
        .filter(SupplierBillItem.supplier_bill_id == bill.id)
        .distinct()
        .all()
    )
    return {row[0] for row in rows}


@router.get("/{document_type}/{document_id}", response_model=RelatedDocumentsResponse)
def get_related_documents(
    document_type: DocumentType,
    document_id: str,
    db: Session = Depends(get_db),
) -> RelatedDocumentsResponse:
    order_ids = _order_ids_for_document(db, document_type, document_id)
    orders = (
        db.query(Order).filter(Order.id.in_(order_ids)).order_by(Order.document_seq.asc()).all()
        if order_ids
        else []
    )
    deliveries = (
        db.query(Delivery).filter(Delivery.order_id.in_(order_ids)).order_by(Delivery.document_seq.asc()).all()
        if order_ids
        else []
    )
    delivery_ids = [row.id for row in deliveries]
    invoice_query = db.query(Invoice).outerjoin(InvoiceItem, InvoiceItem.invoice_id == Invoice.id).outerjoin(
        OrderItem, OrderItem.id == InvoiceItem.order_item_id)
    invoice_filters = []
    if order_ids:
        invoice_filters.append(OrderItem.order_id.in_(order_ids))
    if delivery_ids:
        invoice_filters.append(Invoice.delivery_id.in_(delivery_ids))
    if document_type == "invoice":
        invoice_filters.append(Invoice.id == document_id)
    invoices = (
        invoice_query.filter(or_(*invoice_filters)).distinct().order_by(Invoice.document_seq.asc()).all()
        if invoice_filters
        else []
    )
    bill_query = (
        db.query(SupplierBill)
        .join(SupplierBillItem, SupplierBillItem.supplier_bill_id == SupplierBill.id)
        .join(PurchaseResult, PurchaseResult.id == SupplierBillItem.purchase_result_id)
        .join(SupplierAllocation, SupplierAllocation.id == PurchaseResult.allocation_id)
        .join(OrderItem, OrderItem.id == SupplierAllocation.order_item_id)
    )
    bill_filters = [OrderItem.order_id.in_(order_ids)] if order_ids else []
    if document_type == "supplier_bill":
        bill_filters.append(SupplierBill.id == document_id)
    supplier_bills = (
        bill_query.filter(or_(*bill_filters)).distinct().order_by(SupplierBill.document_seq.asc()).all()
        if bill_filters
        else []
    )
    return RelatedDocumentsResponse(
        orders=[RelatedDocument(type="order", id=row.id, number=row.order_no, status=row.status.value) for row in orders],
        deliveries=[RelatedDocument(type="delivery", id=row.id, number=row.delivery_no) for row in deliveries],
        invoices=[
            RelatedDocument(
                type="invoice",
                id=row.id,
                number=row.official_invoice_no or row.invoice_draft_no or row.invoice_no,
                status=row.status.value,
            )
            for row in invoices
        ],
        supplier_bills=[
            RelatedDocument(type="supplier_bill", id=row.id, number=row.bill_no, status=row.status.value)
            for row in supplier_bills
        ],
    )
