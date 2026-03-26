from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import Invoice, InvoiceStatus, Order
from app.schemas.invoice import (
    InvoiceCreateRequest,
    InvoiceFinalizeResponse,
    InvoiceResetRequest,
    InvoiceResetResponse,
    InvoiceResponse,
    InvoiceUnlockRequest,
    InvoiceUnlockResponse,
)

router = APIRouter(prefix="/api/v1/invoices", tags=["invoices"])


@router.post("", response_model=InvoiceResponse, status_code=201)
def create_invoice(payload: InvoiceCreateRequest, db: Session = Depends(get_db)) -> InvoiceResponse:
    if payload.due_date is not None and payload.due_date < payload.invoice_date:
        raise HTTPException(status_code=422, detail={"code": "INVALID_DATE_RANGE", "message": "due_date must be on or after invoice_date"})

    order = db.query(Order).filter(Order.id == payload.order_id).first()
    if order is None:
        raise HTTPException(status_code=404, detail={"code": "ORDER_NOT_FOUND", "message": "order not found"})

    exists = db.query(Invoice).filter(Invoice.invoice_no == payload.invoice_no).first()
    if exists is not None:
        raise HTTPException(status_code=409, detail={"code": "INVOICE_NO_ALREADY_EXISTS", "message": "invoice_no already exists"})

    row = Invoice(
        invoice_no=payload.invoice_no,
        customer_id=order.customer_id,
        invoice_date=payload.invoice_date,
        delivery_date=order.delivery_date,
        due_date=payload.due_date,
        subtotal=0,
        tax_total=0,
        grand_total=0,
        status=InvoiceStatus.draft,
        is_locked=False,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return InvoiceResponse.model_validate(row)


@router.post("/{invoice_id}/finalize", response_model=InvoiceFinalizeResponse)
def finalize_invoice(invoice_id: int, db: Session = Depends(get_db)) -> InvoiceFinalizeResponse:
    row = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "INVOICE_NOT_FOUND", "message": "invoice not found"})
    if row.status != InvoiceStatus.draft:
        raise HTTPException(status_code=409, detail={"code": "INVOICE_NOT_DRAFT", "message": "invoice is not draft"})

    row.status = InvoiceStatus.finalized
    row.is_locked = True
    db.commit()
    return InvoiceFinalizeResponse(invoice_id=row.id, status=row.status, is_locked=row.is_locked)


@router.post("/{invoice_id}/reset-to-draft", response_model=InvoiceResetResponse)
def reset_to_draft(invoice_id: int, payload: InvoiceResetRequest, db: Session = Depends(get_db)) -> InvoiceResetResponse:
    row = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "INVOICE_NOT_FOUND", "message": "invoice not found"})
    if row.status != InvoiceStatus.finalized:
        raise HTTPException(status_code=409, detail={"code": "INVOICE_NOT_FINALIZED", "message": "invoice is not finalized"})

    row.status = InvoiceStatus.draft
    row.is_locked = False
    db.commit()
    return InvoiceResetResponse(invoice_id=row.id, status=row.status)


@router.post("/{invoice_id}/unlock", response_model=InvoiceUnlockResponse)
def unlock_invoice(invoice_id: int, payload: InvoiceUnlockRequest, db: Session = Depends(get_db)) -> InvoiceUnlockResponse:
    row = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "INVOICE_NOT_FOUND", "message": "invoice not found"})
    if row.status != InvoiceStatus.finalized or not row.is_locked:
        raise HTTPException(
            status_code=409,
            detail={"code": "INVOICE_NOT_LOCKED_FINALIZED", "message": "target must be finalized and locked"},
        )

    row.is_locked = False
    db.commit()
    return InvoiceUnlockResponse(invoice_id=row.id, status=row.status, is_locked=row.is_locked)
