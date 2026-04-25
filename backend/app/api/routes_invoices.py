from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.audit import AuditAction, write_audit_log
from app.db.session import get_db
from app.models.entities import Customer, Invoice, InvoiceItem, InvoiceStatus, LineStatus, Order, OrderItem, PricingBasis, Product, PurchaseResult, SupplierAllocation
from app.schemas.common import ApiErrorResponse
from app.schemas.invoice import (
    InvoiceCreateRequest,
    InvoiceDraftFromPurchaseResultsRequest,
    InvoiceFinalizeResponse,
    InvoiceGenerateRequest,
    InvoiceDraftListRow,
    InvoiceItemResponse,
    InvoiceResetRequest,
    InvoiceResetResponse,
    InvoiceResponse,
    InvoiceUnlockRequest,
    InvoiceUnlockResponse,
)

router = APIRouter(prefix="/api/v1/invoices", tags=["invoices"])

INVOICE_COMMON_ERROR_RESPONSES = {
    422: {"model": ApiErrorResponse, "description": "Validation Error"},
}


def _validate_due_date(invoice_date, due_date) -> None:
    if due_date is not None and due_date < invoice_date:
        raise HTTPException(status_code=422, detail={"code": "INVALID_DATE_RANGE", "message": "due_date must be on or after invoice_date"})


def _get_order_or_404(db: Session, order_id: int) -> Order:
    order = db.query(Order).filter(Order.id == order_id).first()
    if order is None:
        raise HTTPException(status_code=404, detail={"code": "ORDER_NOT_FOUND", "message": "order not found"})
    return order


def _ensure_invoice_no_unique(db: Session, invoice_no: str) -> None:
    exists = db.query(Invoice).filter(Invoice.invoice_no == invoice_no).first()
    if exists is not None:
        raise HTTPException(status_code=409, detail={"code": "INVOICE_NO_ALREADY_EXISTS", "message": "invoice_no already exists"})


def _get_invoice_or_404(db: Session, invoice_id: int) -> Invoice:
    row = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "INVOICE_NOT_FOUND", "message": "invoice not found"})
    return row


def _amount(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@router.post(
    "",
    response_model=InvoiceResponse,
    status_code=201,
    responses={
        **INVOICE_COMMON_ERROR_RESPONSES,
        404: {"model": ApiErrorResponse, "description": "Not Found"},
        409: {"model": ApiErrorResponse, "description": "Conflict"},
    },
)
def create_invoice(payload: InvoiceCreateRequest, db: Session = Depends(get_db)) -> InvoiceResponse:
    _validate_due_date(payload.invoice_date, payload.due_date)
    order = _get_order_or_404(db, payload.order_id)
    _ensure_invoice_no_unique(db, payload.invoice_no)

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
    db.flush()
    write_audit_log(
        db,
        entity_type="invoice",
        entity_id=row.id,
        action=AuditAction.CREATE,
        after={
            "status": row.status.value,
            "is_locked": row.is_locked,
            "subtotal": float(row.subtotal),
            "grand_total": float(row.grand_total),
        },
    )
    db.commit()
    db.refresh(row)
    return InvoiceResponse.model_validate(row)


@router.get("", response_model=list[InvoiceResponse])
def list_invoices(
    order_id: int | None = Query(default=None, gt=0),
    status: InvoiceStatus | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[InvoiceResponse]:
    query = db.query(Invoice)
    if order_id is not None:
        order = _get_order_or_404(db, order_id)
        query = query.filter(Invoice.customer_id == order.customer_id, Invoice.delivery_date == order.delivery_date)
    if status is not None:
        query = query.filter(Invoice.status == status)
    rows = query.order_by(Invoice.id.desc()).all()
    return [InvoiceResponse.model_validate(row) for row in rows]




@router.get("/draft-list", response_model=list[InvoiceDraftListRow])
def list_invoice_draft_rows(db: Session = Depends(get_db)) -> list[InvoiceDraftListRow]:
    rows = (
        db.query(Invoice, InvoiceItem, Customer, Product)
        .join(InvoiceItem, InvoiceItem.invoice_id == Invoice.id)
        .join(OrderItem, OrderItem.id == InvoiceItem.order_item_id)
        .join(Product, Product.id == OrderItem.product_id)
        .join(Customer, Customer.id == Invoice.customer_id)
        .filter(Invoice.status == InvoiceStatus.draft)
        .order_by(Invoice.id.desc(), InvoiceItem.id.asc())
        .all()
    )

    result: list[InvoiceDraftListRow] = []
    for inv, item, customer, product in rows:
        line_amount = float(item.line_amount)
        gross_margin_pct = None
        if line_amount > 0 and item.unit_cost_basis is not None:
            cost_total = float(item.unit_cost_basis) * float(item.billable_qty)
            gross_margin_pct = round(((line_amount - cost_total) / line_amount) * 100, 2)

        result.append(
            InvoiceDraftListRow(
                invoice_id=inv.id,
                invoice_item_id=item.id,
                customer_name=customer.name,
                product_name=product.name,
                billable_qty=float(item.billable_qty),
                billable_uom=item.billable_uom,
                sales_unit_price=float(item.sales_unit_price),
                line_amount=line_amount,
                gross_margin_pct=gross_margin_pct,
            )
        )

    return result
@router.get(
    "/{invoice_id}",
    response_model=InvoiceResponse,
    responses={404: {"model": ApiErrorResponse, "description": "Not Found"}},
)
def get_invoice(invoice_id: int, db: Session = Depends(get_db)) -> InvoiceResponse:
    row = _get_invoice_or_404(db, invoice_id)
    return InvoiceResponse.model_validate(row)


@router.get(
    "/{invoice_id}/items",
    response_model=list[InvoiceItemResponse],
    responses={404: {"model": ApiErrorResponse, "description": "Not Found"}},
)
def list_invoice_items(invoice_id: int, db: Session = Depends(get_db)) -> list[InvoiceItemResponse]:
    _get_invoice_or_404(db, invoice_id)
    rows = db.query(InvoiceItem).filter(InvoiceItem.invoice_id == invoice_id).order_by(InvoiceItem.id.asc()).all()
    return [InvoiceItemResponse.model_validate(row) for row in rows]


@router.post(
    "/generate",
    response_model=InvoiceResponse,
    status_code=201,
    responses={
        **INVOICE_COMMON_ERROR_RESPONSES,
        404: {"model": ApiErrorResponse, "description": "Not Found"},
        409: {"model": ApiErrorResponse, "description": "Conflict"},
    },
)
def generate_invoice(payload: InvoiceGenerateRequest, db: Session = Depends(get_db)) -> InvoiceResponse:
    _validate_due_date(payload.invoice_date, payload.due_date)
    order = _get_order_or_404(db, payload.order_id)
    _ensure_invoice_no_unique(db, payload.invoice_no)

    order_items = db.query(OrderItem).filter(OrderItem.order_id == order.id).all()
    if not order_items:
        raise HTTPException(status_code=422, detail={"code": "ORDER_ITEMS_NOT_FOUND", "message": "order has no items"})

    invoice = Invoice(
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
    db.add(invoice)
    db.flush()

    subtotal = Decimal("0")
    for item in order_items:
        if item.pricing_basis == PricingBasis.uom_kg:
            if item.actual_weight_kg is None:
                raise HTTPException(
                    status_code=422,
                    detail={"code": "MISSING_ACTUAL_WEIGHT", "message": f"actual_weight_kg is required for order_item={item.id}"},
                )
            billable_qty = Decimal(str(item.actual_weight_kg))
            unit_price = item.unit_price_uom_kg
            billable_uom = "kg"
        else:
            billable_qty = Decimal(str(item.ordered_qty))
            unit_price = item.unit_price_uom_count
            billable_uom = "count"

        if unit_price is None:
            raise HTTPException(
                status_code=422,
                detail={"code": "MISSING_UNIT_PRICE", "message": f"unit price is required for order_item={item.id}"},
            )

        sales_unit_price = _amount(Decimal(str(unit_price)))
        line_amount = _amount(billable_qty * sales_unit_price)
        subtotal += line_amount

        db.add(
            InvoiceItem(
                invoice_id=invoice.id,
                order_item_id=item.id,
                billable_qty=float(billable_qty),
                billable_uom=billable_uom,
                invoice_line_status="uninvoiced",
                sales_unit_price=float(sales_unit_price),
                unit_cost_basis=None,
                line_amount=float(line_amount),
                tax_amount=0,
            )
        )

        if item.line_status in {LineStatus.open, LineStatus.allocated, LineStatus.purchased, LineStatus.shipped}:
            item.line_status = LineStatus.invoiced

    invoice.subtotal = float(_amount(subtotal))
    invoice.tax_total = 0
    invoice.grand_total = float(_amount(subtotal))

    write_audit_log(
        db,
        entity_type="invoice",
        entity_id=invoice.id,
        action=AuditAction.CREATE,
        after={
            "status": invoice.status.value,
            "is_locked": invoice.is_locked,
            "subtotal": float(invoice.subtotal),
            "grand_total": float(invoice.grand_total),
            "source_order_id": order.id,
            "generated_item_count": len(order_items),
        },
    )
    db.commit()
    db.refresh(invoice)
    return InvoiceResponse.model_validate(invoice)




@router.post(
    "/generate-draft-from-purchase-results",
    response_model=InvoiceResponse,
    status_code=201,
    responses={
        **INVOICE_COMMON_ERROR_RESPONSES,
        404: {"model": ApiErrorResponse, "description": "Not Found"},
        409: {"model": ApiErrorResponse, "description": "Conflict"},
    },
)
def generate_draft_from_purchase_results(payload: InvoiceDraftFromPurchaseResultsRequest, db: Session = Depends(get_db)) -> InvoiceResponse:
    _validate_due_date(payload.invoice_date, payload.due_date)
    order = _get_order_or_404(db, payload.order_id)
    _ensure_invoice_no_unique(db, payload.invoice_no)

    rows = (
        db.query(PurchaseResult, OrderItem)
        .join(SupplierAllocation, SupplierAllocation.id == PurchaseResult.allocation_id)
        .join(OrderItem, OrderItem.id == SupplierAllocation.order_item_id)
        .filter(OrderItem.order_id == order.id)
        .all()
    )
    if not rows:
        raise HTTPException(status_code=422, detail={"code": "PURCHASE_RESULTS_NOT_FOUND", "message": "order has no purchase results"})

    invoice = Invoice(
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
    db.add(invoice)
    db.flush()

    subtotal = Decimal("0")
    for pr, item in rows:
        billable_qty = Decimal(str(pr.purchased_qty))
        sales_unit_price = Decimal("0")
        if item.pricing_basis == PricingBasis.uom_kg and item.unit_price_uom_kg is not None:
            sales_unit_price = _amount(Decimal(str(item.unit_price_uom_kg)))
        elif item.unit_price_uom_count is not None:
            sales_unit_price = _amount(Decimal(str(item.unit_price_uom_count)))

        line_amount = _amount(billable_qty * sales_unit_price)
        subtotal += line_amount

        db.add(
            InvoiceItem(
                invoice_id=invoice.id,
                order_item_id=item.id,
                billable_qty=float(billable_qty),
                billable_uom=pr.purchased_uom,
                invoice_line_status="uninvoiced",
                sales_unit_price=float(sales_unit_price),
                unit_cost_basis=float(pr.final_unit_cost) if pr.final_unit_cost is not None else None,
                line_amount=float(line_amount),
                tax_amount=0,
            )
        )

    invoice.subtotal = float(_amount(subtotal))
    invoice.tax_total = 0
    invoice.grand_total = float(_amount(subtotal))

    write_audit_log(
        db,
        entity_type="invoice",
        entity_id=invoice.id,
        action=AuditAction.CREATE,
        after={
            "status": invoice.status.value,
            "is_locked": invoice.is_locked,
            "subtotal": float(invoice.subtotal),
            "grand_total": float(invoice.grand_total),
            "source": "purchase_results",
            "source_order_id": order.id,
            "generated_item_count": len(rows),
        },
    )
    db.commit()
    db.refresh(invoice)
    return InvoiceResponse.model_validate(invoice)
@router.post(
    "/{invoice_id}/finalize",
    response_model=InvoiceFinalizeResponse,
    responses={
        **INVOICE_COMMON_ERROR_RESPONSES,
        404: {"model": ApiErrorResponse, "description": "Not Found"},
        409: {"model": ApiErrorResponse, "description": "Conflict"},
    },
)
def finalize_invoice(invoice_id: int, db: Session = Depends(get_db)) -> InvoiceFinalizeResponse:
    row = _get_invoice_or_404(db, invoice_id)
    if row.status != InvoiceStatus.draft:
        raise HTTPException(status_code=409, detail={"code": "INVOICE_NOT_DRAFT", "message": "invoice is not draft"})
    if row.is_locked:
        raise HTTPException(status_code=409, detail={"code": "INVOICE_ALREADY_LOCKED", "message": "invoice is already locked"})

    has_items = db.query(InvoiceItem.id).filter(InvoiceItem.invoice_id == row.id).first() is not None
    if not has_items:
        raise HTTPException(status_code=409, detail={"code": "INVOICE_ITEMS_REQUIRED", "message": "invoice must have at least one item"})

    before = {"status": row.status.value, "is_locked": row.is_locked}
    row.status = InvoiceStatus.finalized
    row.is_locked = True
    db.flush()
    write_audit_log(
        db,
        entity_type="invoice",
        entity_id=row.id,
        action=AuditAction.FINALIZE,
        before=before,
        after={"status": row.status.value, "is_locked": row.is_locked},
    )
    db.commit()
    return InvoiceFinalizeResponse(invoice_id=row.id, status=row.status, is_locked=row.is_locked)


@router.post(
    "/{invoice_id}/reset-to-draft",
    response_model=InvoiceResetResponse,
    responses={
        **INVOICE_COMMON_ERROR_RESPONSES,
        404: {"model": ApiErrorResponse, "description": "Not Found"},
        409: {"model": ApiErrorResponse, "description": "Conflict"},
    },
)
def reset_to_draft(invoice_id: int, payload: InvoiceResetRequest, db: Session = Depends(get_db)) -> InvoiceResetResponse:
    row = _get_invoice_or_404(db, invoice_id)
    if row.status != InvoiceStatus.finalized:
        raise HTTPException(status_code=409, detail={"code": "INVOICE_NOT_FINALIZED", "message": "invoice is not finalized"})

    before = {"status": row.status.value, "is_locked": row.is_locked}
    row.status = InvoiceStatus.draft
    row.is_locked = False
    db.flush()
    write_audit_log(
        db,
        entity_type="invoice",
        entity_id=row.id,
        action=AuditAction.RESET_TO_DRAFT,
        reason_code=payload.reset_reason_code,
        before=before,
        after={"status": row.status.value, "is_locked": row.is_locked},
    )
    db.commit()
    return InvoiceResetResponse(invoice_id=row.id, status=row.status)


@router.post(
    "/{invoice_id}/unlock",
    response_model=InvoiceUnlockResponse,
    responses={
        **INVOICE_COMMON_ERROR_RESPONSES,
        404: {"model": ApiErrorResponse, "description": "Not Found"},
        409: {"model": ApiErrorResponse, "description": "Conflict"},
    },
)
def unlock_invoice(invoice_id: int, payload: InvoiceUnlockRequest, db: Session = Depends(get_db)) -> InvoiceUnlockResponse:
    row = _get_invoice_or_404(db, invoice_id)
    if row.status != InvoiceStatus.finalized or not row.is_locked:
        raise HTTPException(
            status_code=409,
            detail={"code": "INVOICE_NOT_LOCKED_FINALIZED", "message": "target must be finalized and locked"},
        )

    before = {"status": row.status.value, "is_locked": row.is_locked}
    row.is_locked = False
    db.flush()
    write_audit_log(
        db,
        entity_type="invoice",
        entity_id=row.id,
        action=AuditAction.UNLOCK,
        reason_code=payload.unlock_reason_code,
        before=before,
        after={"status": row.status.value, "is_locked": row.is_locked},
    )
    db.commit()
    return InvoiceUnlockResponse(invoice_id=row.id, status=row.status, is_locked=row.is_locked)
