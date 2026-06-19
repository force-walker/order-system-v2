from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.audit import AuditAction, write_audit_log
from app.core.invoice_pdf import InvoicePdfDocument, InvoicePdfLine, build_invoice_pdf
from app.core.invoice_pricing import compute_draft_margin, compute_hkd_purchase_unit_cost, get_system_settings_or_404
from app.core.numbering import (
    ensure_invoice_item_number,
    generate_invoice_draft_no,
    generate_official_invoice_no,
)
from app.db.session import get_db
from app.models.entities import Customer, Invoice, InvoiceItem, InvoiceStatus, LineStatus, Order, OrderItem, OrderStatus, PricingBasis, Product, PurchaseResult, SupplierAllocation
from app.schemas.common import ApiErrorResponse
from app.schemas.invoice import (
    InvoiceBatchFinalizeRequest,
    InvoiceBatchFinalizeResponse,
    InvoiceBatchFinalizeResult,
    InvoiceCreateRequest,
    InvoiceDraftFromPurchaseResultsRequest,
    InvoiceDraftGenerateResult,
    InvoiceDraftListRow,
    InvoiceDraftRecalculateResponse,
    InvoiceFinalizeResponse,
    InvoiceGenerateRequest,
    InvoiceItemResponse,
    InvoiceItemUpdateRequest,
    InvoiceNeighborsResponse,
    InvoiceReportLine,
    InvoiceReportResponse,
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


def _get_order_by_uuid_or_404(db: Session, order_uuid: str) -> Order:
    order = db.query(Order).filter(Order.uuid == order_uuid).first()
    if order is None:
        raise HTTPException(status_code=404, detail={"code": "ORDER_NOT_FOUND", "message": "order not found"})
    return order


def _get_invoice_or_404(db: Session, invoice_id: int) -> Invoice:
    row = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "INVOICE_NOT_FOUND", "message": "invoice not found"})
    return row


def _get_invoice_by_uuid_or_404(db: Session, invoice_uuid: str) -> Invoice:
    row = db.query(Invoice).filter(Invoice.uuid == invoice_uuid).first()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "INVOICE_NOT_FOUND", "message": "invoice not found"})
    return row


def _get_invoice_item_or_404(db: Session, invoice_id: int, invoice_item_id: int) -> InvoiceItem:
    item = db.query(InvoiceItem).filter(InvoiceItem.id == invoice_item_id, InvoiceItem.invoice_id == invoice_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail={"code": "INVOICE_ITEM_NOT_FOUND", "message": "invoice item not found"})
    return item


def _get_invoice_item_by_uuid_or_404(db: Session, invoice_id: int, invoice_item_uuid: str) -> InvoiceItem:
    item = db.query(InvoiceItem).filter(InvoiceItem.uuid == invoice_item_uuid, InvoiceItem.invoice_id == invoice_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail={"code": "INVOICE_ITEM_NOT_FOUND", "message": "invoice item not found"})
    return item


def _amount(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _compute_auto_sales_unit_price(purchase_unit_cost: Decimal | None) -> tuple[Decimal, str | None]:
    if purchase_unit_cost is None:
        return Decimal("0.00"), "仕入単価が未設定のため自動計算できません"
    # sales_unit_price = (purchase_unit_cost / 20 + 50) / 0.75
    price = ((purchase_unit_cost / Decimal("20")) + Decimal("50")) / Decimal("0.75")
    return _amount(price), None


def _draft_item_metrics(item: InvoiceItem) -> tuple[float | None, bool]:
    margin = compute_draft_margin(
        sales_unit_price=Decimal(str(item.sales_unit_price)),
        unit_cost_basis=(Decimal(str(item.unit_cost_basis)) if item.unit_cost_basis is not None else None),
    )
    return margin.gross_margin_pct, margin.gross_margin_unavailable


def _invoice_item_response(item: InvoiceItem) -> InvoiceItemResponse:
    gross_margin_pct, gross_margin_unavailable = _draft_item_metrics(item)
    return InvoiceItemResponse(
        id=item.id,
        uuid=item.uuid,
        invoice_id=item.invoice_id,
        order_item_id=item.order_item_id,
        invoice_line_no=item.invoice_line_no,
        billable_qty=float(item.billable_qty),
        billable_uom=item.billable_uom,
        invoice_line_status=item.invoice_line_status,
        sales_unit_price=float(item.sales_unit_price),
        unit_cost_basis=(float(item.unit_cost_basis) if item.unit_cost_basis is not None else None),
        auto_price_error=("仕入単価が未設定のため自動計算できません" if item.unit_cost_basis is None else None),
        line_amount=float(item.line_amount),
        tax_amount=float(item.tax_amount),
        gross_margin_pct=gross_margin_pct,
        gross_margin_unavailable=gross_margin_unavailable,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _assign_invoice_header_numbers(db: Session, invoice: Invoice, order: Order) -> None:
    if (
        invoice.tracking_no
        and invoice.invoice_draft_no
        and invoice.invoice_no
        and not invoice.invoice_no.startswith("pending-")
    ):
        return
    tracking_no, draft_no = generate_invoice_draft_no(db, order)
    invoice.tracking_no = invoice.tracking_no or tracking_no
    invoice.invoice_draft_no = invoice.invoice_draft_no or draft_no
    if not invoice.invoice_no or invoice.invoice_no.startswith("pending-"):
        invoice.invoice_no = invoice.invoice_draft_no


def _recalc_invoice_totals(db: Session, invoice: Invoice) -> None:
    items = db.query(InvoiceItem).filter(InvoiceItem.invoice_id == invoice.id).all()
    subtotal = Decimal("0")
    tax_total = Decimal("0")
    for item in items:
        subtotal += Decimal(str(item.line_amount))
        tax_total += Decimal(str(item.tax_amount))

    invoice.subtotal = float(_amount(subtotal))
    invoice.tax_total = float(_amount(tax_total))
    invoice.grand_total = float(_amount(subtotal + tax_total))


def _recalculate_draft_invoice_costs(db: Session, invoice: Invoice) -> int:
    rows = (
        db.query(InvoiceItem, OrderItem, Product)
        .join(OrderItem, OrderItem.id == InvoiceItem.order_item_id)
        .join(Product, Product.id == OrderItem.product_id)
        .filter(InvoiceItem.invoice_id == invoice.id)
        .order_by(InvoiceItem.id.asc())
        .all()
    )
    settings = get_system_settings_or_404(db)
    recalculated_count = 0

    for item, _order_item, product in rows:
        old_basis = Decimal(str(item.unit_cost_basis)) if item.unit_cost_basis is not None else None
        if item.source_purchase_unit_cost_jpy is None:
            new_basis = None
        else:
            new_basis = compute_hkd_purchase_unit_cost(
                jpy_purchase_unit_cost=Decimal(str(item.source_purchase_unit_cost_jpy)),
                freight_weight=(Decimal(str(product.freight_weight)) if product.freight_weight is not None else None),
                settings=settings,
            )

        if old_basis != new_basis:
            item.unit_cost_basis = float(new_basis) if new_basis is not None else None
            recalculated_count += 1
        if Decimal(str(item.tax_amount)) != Decimal("0"):
            item.tax_amount = 0

    _recalc_invoice_totals(db, invoice)
    return recalculated_count


def _sync_order_statuses_for_invoice(db: Session, invoice: Invoice) -> None:
    order_ids = {
        order_id
        for (order_id,) in (
            db.query(OrderItem.order_id)
            .join(InvoiceItem, InvoiceItem.order_item_id == OrderItem.id)
            .filter(InvoiceItem.invoice_id == invoice.id)
            .distinct()
            .all()
        )
    }
    if not order_ids:
        return

    for order_id in order_ids:
        lines = db.query(OrderItem).filter(OrderItem.order_id == order_id).order_by(OrderItem.id.asc()).all()
        for line in lines:
            has_finalized_invoice = (
                db.query(InvoiceItem.id)
                .join(Invoice, Invoice.id == InvoiceItem.invoice_id)
                .filter(InvoiceItem.order_item_id == line.id, Invoice.status == InvoiceStatus.finalized)
                .first()
                is not None
            )
            target_line_status = LineStatus.invoiced if has_finalized_invoice else LineStatus.shipped
            if target_line_status == line.line_status:
                continue

            before = {"line_status": line.line_status.value}
            line.line_status = target_line_status
            write_audit_log(
                db,
                entity_type="order_item",
                entity_id=line.id,
                action=AuditAction.UPDATE,
                before=before,
                after={"line_status": line.line_status.value, "order_id": line.order_id},
            )

        order = db.query(Order).filter(Order.id == order_id).first()
        if order is None:
            continue
        all_invoiced = bool(lines) and all(line.line_status == LineStatus.invoiced for line in lines)
        if all_invoiced:
            target_order_status = OrderStatus.invoiced
        elif lines:
            target_order_status = OrderStatus.shipped
        else:
            target_order_status = order.status

        if target_order_status != order.status:
            before = {"order_status": order.status.value}
            order.status = target_order_status
            order.updated_by = "system_api"
            write_audit_log(
                db,
                entity_type="order",
                entity_id=order.id,
                action=AuditAction.UPDATE,
                before=before,
                after={"order_status": order.status.value},
            )


def _finalize_invoice_row(db: Session, invoice: Invoice, *, reason_code: str | None = None) -> InvoiceFinalizeResponse:
    if invoice.status != InvoiceStatus.draft:
        raise HTTPException(status_code=409, detail={"code": "INVOICE_NOT_DRAFT", "message": "invoice is not draft"})
    if invoice.is_locked:
        raise HTTPException(status_code=409, detail={"code": "INVOICE_ALREADY_LOCKED", "message": "invoice is already locked"})

    has_items = db.query(InvoiceItem.id).filter(InvoiceItem.invoice_id == invoice.id).first() is not None
    if not has_items:
        raise HTTPException(status_code=409, detail={"code": "INVOICE_ITEMS_REQUIRED", "message": "invoice must have at least one item"})

    before = {"status": invoice.status.value, "is_locked": invoice.is_locked}
    if invoice.official_invoice_no is None:
        invoice.official_invoice_no = generate_official_invoice_no(db, invoice)
    invoice.invoice_no = invoice.official_invoice_no
    invoice.status = InvoiceStatus.finalized
    invoice.is_locked = True
    db.flush()
    _sync_order_statuses_for_invoice(db, invoice)
    write_audit_log(
        db,
        entity_type="invoice",
        entity_id=invoice.id,
        action=AuditAction.FINALIZE,
        reason_code=reason_code,
        before=before,
        after={"status": invoice.status.value, "is_locked": invoice.is_locked},
    )
    return InvoiceFinalizeResponse(
        invoice_id=invoice.id,
        invoice_no=invoice.invoice_no,
        official_invoice_no=invoice.official_invoice_no,
        status=invoice.status,
        is_locked=invoice.is_locked,
    )


def _payment_terms_label(invoice: Invoice) -> str:
    if invoice.due_date is None:
        return "Not specified"
    return f"Due on {invoice.due_date.strftime('%m/%d/%Y')}"


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

    row = Invoice(
        invoice_no=f"pending-{datetime.now().timestamp()}-{order.id}",
        customer_id=order.customer_id,
        tracking_no=order.tracking_no,
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
    _assign_invoice_header_numbers(db, row, order)
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
    order_uuid: str | None = Query(default=None),
    status: InvoiceStatus | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[InvoiceResponse]:
    query = db.query(Invoice)
    if order_id is not None:
        order = _get_order_or_404(db, order_id)
        if order.tracking_no is not None:
            query = query.filter(Invoice.tracking_no == order.tracking_no)
        else:
            query = query.filter(Invoice.customer_id == order.customer_id, Invoice.delivery_date == order.delivery_date)
    if order_uuid is not None:
        order = _get_order_by_uuid_or_404(db, order_uuid)
        if order.tracking_no is not None:
            query = query.filter(Invoice.tracking_no == order.tracking_no)
        else:
            query = query.filter(Invoice.customer_id == order.customer_id, Invoice.delivery_date == order.delivery_date)
    if status is not None:
        query = query.filter(Invoice.status == status)
    rows = query.order_by(Invoice.id.desc()).all()
    return [InvoiceResponse.model_validate(row) for row in rows]


@router.get("/draft-list", response_model=list[InvoiceDraftListRow])
def list_invoice_draft_rows(db: Session = Depends(get_db)) -> list[InvoiceDraftListRow]:
    rows = (
        db.query(Invoice, InvoiceItem, Customer, Product, Order)
        .join(InvoiceItem, InvoiceItem.invoice_id == Invoice.id)
        .join(OrderItem, OrderItem.id == InvoiceItem.order_item_id)
        .join(Order, Order.id == OrderItem.order_id)
        .join(Product, Product.id == OrderItem.product_id)
        .join(Customer, Customer.id == Invoice.customer_id)
        .filter(Invoice.status == InvoiceStatus.draft)
        .order_by(Order.order_no.asc(), InvoiceItem.id.asc())
        .all()
    )

    result: list[InvoiceDraftListRow] = []
    for inv, item, customer, product, order in rows:
        gross_margin_pct, gross_margin_unavailable = _draft_item_metrics(item)
        line_amount = float(item.line_amount)
        unit_cost_basis = float(item.unit_cost_basis) if item.unit_cost_basis is not None else None
        result.append(
            InvoiceDraftListRow(
                invoice_id=inv.id,
                invoice_item_id=item.id,
                invoice_uuid=inv.uuid,
                invoice_item_uuid=item.uuid,
                tracking_no=inv.tracking_no,
                invoice_no=inv.invoice_no,
                invoice_draft_no=inv.invoice_draft_no,
                official_invoice_no=inv.official_invoice_no,
                invoice_line_no=item.invoice_line_no,
                invoice_date=inv.invoice_date,
                delivery_date=inv.delivery_date,
                status=inv.status,
                order_no=order.order_no,
                customer_name=customer.name,
                product_name=product.name,
                billable_qty=float(item.billable_qty),
                billable_uom=item.billable_uom,
                sales_unit_price=float(item.sales_unit_price),
                unit_cost_basis=unit_cost_basis,
                auto_price_error=("仕入単価が未設定のため自動計算できません" if unit_cost_basis is None else None),
                line_amount=line_amount,
                gross_margin_pct=gross_margin_pct,
                gross_margin_unavailable=gross_margin_unavailable,
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
    "/uuid/{invoice_uuid}",
    response_model=InvoiceResponse,
    responses={404: {"model": ApiErrorResponse, "description": "Not Found"}},
)
def get_invoice_by_uuid(invoice_uuid: str, db: Session = Depends(get_db)) -> InvoiceResponse:
    row = _get_invoice_by_uuid_or_404(db, invoice_uuid)
    return InvoiceResponse.model_validate(row)


@router.get(
    "/{invoice_id}/items",
    response_model=list[InvoiceItemResponse],
    responses={404: {"model": ApiErrorResponse, "description": "Not Found"}},
)
def list_invoice_items(invoice_id: int, db: Session = Depends(get_db)) -> list[InvoiceItemResponse]:
    _get_invoice_or_404(db, invoice_id)
    rows = db.query(InvoiceItem).filter(InvoiceItem.invoice_id == invoice_id).order_by(InvoiceItem.id.asc()).all()
    return [_invoice_item_response(row) for row in rows]


@router.get(
    "/uuid/{invoice_uuid}/items",
    response_model=list[InvoiceItemResponse],
    responses={404: {"model": ApiErrorResponse, "description": "Not Found"}},
)
def list_invoice_items_by_uuid(invoice_uuid: str, db: Session = Depends(get_db)) -> list[InvoiceItemResponse]:
    invoice = _get_invoice_by_uuid_or_404(db, invoice_uuid)
    rows = db.query(InvoiceItem).filter(InvoiceItem.invoice_id == invoice.id).order_by(InvoiceItem.id.asc()).all()
    return [_invoice_item_response(row) for row in rows]


@router.get(
    "/{invoice_id}/neighbors",
    response_model=InvoiceNeighborsResponse,
    responses={404: {"model": ApiErrorResponse, "description": "Not Found"}},
)
def get_invoice_neighbors(invoice_id: int, db: Session = Depends(get_db)) -> InvoiceNeighborsResponse:
    _get_invoice_or_404(db, invoice_id)
    ordered_ids = [row_id for (row_id,) in db.query(Invoice.id).order_by(Invoice.id.desc()).all()]
    idx = ordered_ids.index(invoice_id)

    prev_invoice_id = ordered_ids[idx - 1] if idx > 0 else None
    next_invoice_id = ordered_ids[idx + 1] if idx < len(ordered_ids) - 1 else None

    return InvoiceNeighborsResponse(
        invoice_id=invoice_id,
        prev_invoice_id=prev_invoice_id,
        next_invoice_id=next_invoice_id,
    )


@router.get(
    "/{invoice_id}/report",
    response_model=InvoiceReportResponse,
    responses={404: {"model": ApiErrorResponse, "description": "Not Found"}},
)
def get_invoice_report(invoice_id: int, db: Session = Depends(get_db)) -> InvoiceReportResponse:
    invoice = _get_invoice_or_404(db, invoice_id)
    customer = db.query(Customer).filter(Customer.id == invoice.customer_id).first()
    if customer is None:
        raise HTTPException(status_code=404, detail={"code": "CUSTOMER_NOT_FOUND", "message": "customer not found"})

    items = db.query(InvoiceItem).filter(InvoiceItem.invoice_id == invoice_id).order_by(InvoiceItem.id.asc()).all()
    product_name_by_order_item_id = {
        oi.id: name
        for oi, name in (
            db.query(OrderItem, Product.name)
            .join(Product, Product.id == OrderItem.product_id)
            .filter(OrderItem.id.in_([i.order_item_id for i in items]))
            .all()
        )
    }

    return InvoiceReportResponse(
        invoice_id=invoice.id,
        invoice_uuid=invoice.uuid,
        tracking_no=invoice.tracking_no,
        invoice_no=invoice.invoice_no,
        invoice_draft_no=invoice.invoice_draft_no,
        official_invoice_no=invoice.official_invoice_no,
        status=invoice.status,
        customer_id=customer.id,
        customer_name=customer.name,
        invoice_date=invoice.invoice_date,
        delivery_date=invoice.delivery_date,
        due_date=invoice.due_date,
        subtotal=float(invoice.subtotal),
        tax_total=float(invoice.tax_total),
        grand_total=float(invoice.grand_total),
        items=[
            InvoiceReportLine(
                invoice_item_id=i.id,
                invoice_item_uuid=i.uuid,
                order_item_id=i.order_item_id,
                invoice_line_no=i.invoice_line_no,
                product_name=product_name_by_order_item_id.get(i.order_item_id, "-"),
                billable_qty=float(i.billable_qty),
                billable_uom=i.billable_uom,
                sales_unit_price=float(i.sales_unit_price),
                unit_cost_basis=(float(i.unit_cost_basis) if i.unit_cost_basis is not None else None),
                line_amount=float(i.line_amount),
                tax_amount=float(i.tax_amount),
                gross_margin_pct=_draft_item_metrics(i)[0],
                gross_margin_unavailable=_draft_item_metrics(i)[1],
            )
            for i in items
        ],
    )


@router.get(
    "/uuid/{invoice_uuid}/report",
    response_model=InvoiceReportResponse,
    responses={404: {"model": ApiErrorResponse, "description": "Not Found"}},
)
def get_invoice_report_by_uuid(invoice_uuid: str, db: Session = Depends(get_db)) -> InvoiceReportResponse:
    invoice = _get_invoice_by_uuid_or_404(db, invoice_uuid)
    customer = db.query(Customer).filter(Customer.id == invoice.customer_id).first()
    if customer is None:
        raise HTTPException(status_code=404, detail={"code": "CUSTOMER_NOT_FOUND", "message": "customer not found"})

    items = db.query(InvoiceItem).filter(InvoiceItem.invoice_id == invoice.id).order_by(InvoiceItem.id.asc()).all()
    product_name_by_order_item_id = {
        oi.id: name
        for oi, name in (
            db.query(OrderItem, Product.name)
            .join(Product, Product.id == OrderItem.product_id)
            .filter(OrderItem.id.in_([i.order_item_id for i in items]))
            .all()
        )
    }

    return InvoiceReportResponse(
        invoice_id=invoice.id,
        invoice_uuid=invoice.uuid,
        tracking_no=invoice.tracking_no,
        invoice_no=invoice.invoice_no,
        invoice_draft_no=invoice.invoice_draft_no,
        official_invoice_no=invoice.official_invoice_no,
        status=invoice.status,
        customer_id=customer.id,
        customer_name=customer.name,
        invoice_date=invoice.invoice_date,
        delivery_date=invoice.delivery_date,
        due_date=invoice.due_date,
        subtotal=float(invoice.subtotal),
        tax_total=float(invoice.tax_total),
        grand_total=float(invoice.grand_total),
        items=[
            InvoiceReportLine(
                invoice_item_id=i.id,
                invoice_item_uuid=i.uuid,
                order_item_id=i.order_item_id,
                invoice_line_no=i.invoice_line_no,
                product_name=product_name_by_order_item_id.get(i.order_item_id, "-"),
                billable_qty=float(i.billable_qty),
                billable_uom=i.billable_uom,
                sales_unit_price=float(i.sales_unit_price),
                unit_cost_basis=(float(i.unit_cost_basis) if i.unit_cost_basis is not None else None),
                line_amount=float(i.line_amount),
                tax_amount=float(i.tax_amount),
                gross_margin_pct=_draft_item_metrics(i)[0],
                gross_margin_unavailable=_draft_item_metrics(i)[1],
            )
            for i in items
        ],
    )


@router.get(
    "/{invoice_id}/pdf",
    responses={
        200: {"content": {"application/pdf": {}}},
        404: {"model": ApiErrorResponse, "description": "Not Found"},
        409: {"model": ApiErrorResponse, "description": "Conflict"},
    },
)
def get_invoice_pdf(invoice_id: int, db: Session = Depends(get_db)) -> Response:
    invoice = _get_invoice_or_404(db, invoice_id)
    customer = db.query(Customer).filter(Customer.id == invoice.customer_id).first()
    if customer is None:
        raise HTTPException(status_code=404, detail={"code": "CUSTOMER_NOT_FOUND", "message": "customer not found"})

    rows = (
        db.query(InvoiceItem, OrderItem, Product, Order)
        .join(OrderItem, OrderItem.id == InvoiceItem.order_item_id)
        .join(Product, Product.id == OrderItem.product_id)
        .join(Order, Order.id == OrderItem.order_id)
        .filter(InvoiceItem.invoice_id == invoice_id)
        .order_by(InvoiceItem.id.asc())
        .all()
    )
    if not rows:
        raise HTTPException(status_code=409, detail={"code": "INVOICE_ITEMS_REQUIRED", "message": "invoice must have at least one item"})

    customer_address_lines = [line for line in [customer.region] if line]
    doc = InvoicePdfDocument(
        invoice_no=invoice.invoice_no,
        invoice_date=invoice.invoice_date,
        due_date=invoice.due_date,
        customer_name=customer.name,
        customer_address_lines=customer_address_lines,
        untaxed_amount=float(invoice.subtotal),
        total=float(invoice.grand_total),
        tax_total=float(invoice.tax_total),
        payment_terms=_payment_terms_label(invoice),
        payment_communication=invoice.invoice_no,
        lines=[
            InvoicePdfLine(
                description=product.name,
                source=order.order_no,
                quantity=float(item.billable_qty),
                unit_price=float(item.sales_unit_price),
                amount=float(item.line_amount),
            )
            for item, _order_item, product, order in rows
        ],
    )
    pdf_bytes = build_invoice_pdf(doc)
    headers = {"Content-Disposition": f'inline; filename="{invoice.invoice_no}.pdf"'}
    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)


@router.get(
    "/uuid/{invoice_uuid}/pdf",
    responses={
        200: {"content": {"application/pdf": {}}},
        404: {"model": ApiErrorResponse, "description": "Not Found"},
        409: {"model": ApiErrorResponse, "description": "Conflict"},
    },
)
def get_invoice_pdf_by_uuid(invoice_uuid: str, db: Session = Depends(get_db)) -> Response:
    invoice = _get_invoice_by_uuid_or_404(db, invoice_uuid)
    return get_invoice_pdf(invoice.id, db)


@router.patch(
    "/{invoice_id}/items/{invoice_item_id}",
    response_model=InvoiceItemResponse,
    responses={
        **INVOICE_COMMON_ERROR_RESPONSES,
        404: {"model": ApiErrorResponse, "description": "Not Found"},
        409: {"model": ApiErrorResponse, "description": "Conflict"},
    },
)
def update_invoice_draft_item(
    invoice_id: int,
    invoice_item_id: int,
    payload: InvoiceItemUpdateRequest,
    db: Session = Depends(get_db),
) -> InvoiceItemResponse:
    invoice = _get_invoice_or_404(db, invoice_id)
    if invoice.status != InvoiceStatus.draft:
        raise HTTPException(status_code=409, detail={"code": "INVOICE_NOT_DRAFT", "message": "invoice is not draft"})

    item = _get_invoice_item_or_404(db, invoice_id, invoice_item_id)

    order_item = db.query(OrderItem).filter(OrderItem.id == item.order_item_id).first()
    if order_item is None:
        raise HTTPException(status_code=404, detail={"code": "ORDER_ITEM_NOT_FOUND", "message": "order item not found"})

    before = {
        "billable_qty": float(item.billable_qty),
        "sales_unit_price": float(item.sales_unit_price),
        "line_amount": float(item.line_amount),
        "tax_amount": float(item.tax_amount),
    }

    billable_qty = Decimal(str(payload.billable_qty))
    sales_unit_price = Decimal(str(payload.sales_unit_price))
    line_amount = _amount(billable_qty * sales_unit_price)

    tax_amount = Decimal("0")

    item.billable_qty = float(billable_qty)
    if payload.billable_uom is not None:
        item.billable_uom = payload.billable_uom
    item.sales_unit_price = float(_amount(sales_unit_price))
    item.line_amount = float(line_amount)
    item.tax_amount = float(tax_amount)

    _recalc_invoice_totals(db, invoice)
    db.flush()

    write_audit_log(
        db,
        entity_type="invoice",
        entity_id=invoice.id,
        action=AuditAction.UPDATE,
        before=before,
        after={
            "billable_qty": float(item.billable_qty),
            "sales_unit_price": float(item.sales_unit_price),
            "line_amount": float(item.line_amount),
            "tax_amount": float(item.tax_amount),
            "invoice_subtotal": float(invoice.subtotal),
            "invoice_tax_total": float(invoice.tax_total),
            "invoice_grand_total": float(invoice.grand_total),
        },
    )

    db.commit()
    db.refresh(item)
    return _invoice_item_response(item)


@router.patch(
    "/uuid/{invoice_uuid}/items/{invoice_item_uuid}",
    response_model=InvoiceItemResponse,
    responses={
        **INVOICE_COMMON_ERROR_RESPONSES,
        404: {"model": ApiErrorResponse, "description": "Not Found"},
        409: {"model": ApiErrorResponse, "description": "Conflict"},
    },
)
def update_invoice_draft_item_by_uuid(
    invoice_uuid: str,
    invoice_item_uuid: str,
    payload: InvoiceItemUpdateRequest,
    db: Session = Depends(get_db),
) -> InvoiceItemResponse:
    invoice = _get_invoice_by_uuid_or_404(db, invoice_uuid)
    if invoice.status != InvoiceStatus.draft:
        raise HTTPException(status_code=409, detail={"code": "INVOICE_NOT_DRAFT", "message": "invoice is not draft"})

    item = _get_invoice_item_by_uuid_or_404(db, invoice.id, invoice_item_uuid)
    order_item = db.query(OrderItem).filter(OrderItem.id == item.order_item_id).first()
    if order_item is None:
        raise HTTPException(status_code=404, detail={"code": "ORDER_ITEM_NOT_FOUND", "message": "order item not found"})

    before = {
        "billable_qty": float(item.billable_qty),
        "sales_unit_price": float(item.sales_unit_price),
        "line_amount": float(item.line_amount),
        "tax_amount": float(item.tax_amount),
    }

    billable_qty = Decimal(str(payload.billable_qty))
    sales_unit_price = Decimal(str(payload.sales_unit_price))
    line_amount = _amount(billable_qty * sales_unit_price)
    tax_amount = Decimal("0")

    item.billable_qty = float(billable_qty)
    if payload.billable_uom is not None:
        item.billable_uom = payload.billable_uom
    item.sales_unit_price = float(_amount(sales_unit_price))
    item.line_amount = float(line_amount)
    item.tax_amount = float(tax_amount)

    _recalc_invoice_totals(db, invoice)
    db.flush()

    write_audit_log(
        db,
        entity_type="invoice",
        entity_id=invoice.id,
        action=AuditAction.UPDATE,
        before=before,
        after={
            "billable_qty": float(item.billable_qty),
            "sales_unit_price": float(item.sales_unit_price),
            "line_amount": float(item.line_amount),
            "tax_amount": float(item.tax_amount),
            "invoice_subtotal": float(invoice.subtotal),
            "invoice_tax_total": float(invoice.tax_total),
            "invoice_grand_total": float(invoice.grand_total),
        },
    )

    db.commit()
    db.refresh(item)
    return _invoice_item_response(item)


@router.post(
    "/{invoice_id}/items/{invoice_item_id}/finalize",
    response_model=InvoiceItemResponse,
    responses={
        404: {"model": ApiErrorResponse, "description": "Not Found"},
        409: {"model": ApiErrorResponse, "description": "Conflict"},
    },
)
def finalize_invoice_item_line(invoice_id: int, invoice_item_id: int, db: Session = Depends(get_db)) -> InvoiceItemResponse:
    invoice = _get_invoice_or_404(db, invoice_id)
    if invoice.status != InvoiceStatus.draft:
        raise HTTPException(status_code=409, detail={"code": "INVOICE_NOT_DRAFT", "message": "invoice is not draft"})

    item = _get_invoice_item_or_404(db, invoice_id, invoice_item_id)
    if item.invoice_line_status == "invoiced":
        raise HTTPException(status_code=409, detail={"code": "INVOICE_ITEM_ALREADY_INVOICED", "message": "invoice item already invoiced"})

    before = {"invoice_line_status": item.invoice_line_status}
    item.invoice_line_status = "invoiced"
    db.flush()

    write_audit_log(
        db,
        entity_type="invoice",
        entity_id=invoice.id,
        action=AuditAction.UPDATE,
        before=before,
        after={"invoice_line_status": item.invoice_line_status, "invoice_item_id": item.id},
    )

    db.commit()
    db.refresh(item)
    return _invoice_item_response(item)


@router.post(
    "/uuid/{invoice_uuid}/items/{invoice_item_uuid}/finalize",
    response_model=InvoiceItemResponse,
    responses={
        404: {"model": ApiErrorResponse, "description": "Not Found"},
        409: {"model": ApiErrorResponse, "description": "Conflict"},
    },
)
def finalize_invoice_item_line_by_uuid(invoice_uuid: str, invoice_item_uuid: str, db: Session = Depends(get_db)) -> InvoiceItemResponse:
    invoice = _get_invoice_by_uuid_or_404(db, invoice_uuid)
    if invoice.status != InvoiceStatus.draft:
        raise HTTPException(status_code=409, detail={"code": "INVOICE_NOT_DRAFT", "message": "invoice is not draft"})

    item = _get_invoice_item_by_uuid_or_404(db, invoice.id, invoice_item_uuid)
    if item.invoice_line_status == "invoiced":
        raise HTTPException(status_code=409, detail={"code": "INVOICE_ITEM_ALREADY_INVOICED", "message": "invoice item already invoiced"})

    before = {"invoice_line_status": item.invoice_line_status}
    item.invoice_line_status = "invoiced"
    db.flush()

    write_audit_log(
        db,
        entity_type="invoice",
        entity_id=invoice.id,
        action=AuditAction.UPDATE,
        before=before,
        after={"invoice_line_status": item.invoice_line_status, "invoice_item_id": item.id},
    )

    db.commit()
    db.refresh(item)
    return _invoice_item_response(item)


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

    order_items = db.query(OrderItem).filter(OrderItem.order_id == order.id).all()
    if not order_items:
        raise HTTPException(status_code=422, detail={"code": "ORDER_ITEMS_NOT_FOUND", "message": "order has no items"})

    invoice = Invoice(
        invoice_no=f"pending-{datetime.now().timestamp()}-{order.id}",
        customer_id=order.customer_id,
        tracking_no=order.tracking_no,
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
    _assign_invoice_header_numbers(db, invoice, order)

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

        invoice_item = InvoiceItem(
            invoice_id=invoice.id,
            order_item_id=item.id,
            billable_qty=float(billable_qty),
            billable_uom=billable_uom,
            invoice_line_status="uninvoiced",
            sales_unit_price=float(sales_unit_price),
            unit_cost_basis=None,
            source_purchase_unit_cost_jpy=None,
            line_amount=float(line_amount),
            tax_amount=0,
        )
        db.add(invoice_item)
        db.flush()
        ensure_invoice_item_number(db, invoice, invoice_item)

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
    response_model=InvoiceDraftGenerateResult,
    status_code=201,
    responses={
        **INVOICE_COMMON_ERROR_RESPONSES,
        404: {"model": ApiErrorResponse, "description": "Not Found"},
        409: {"model": ApiErrorResponse, "description": "Conflict"},
    },
)
def generate_draft_from_purchase_results(payload: InvoiceDraftFromPurchaseResultsRequest, db: Session = Depends(get_db)) -> InvoiceDraftGenerateResult:
    _validate_due_date(payload.invoice_date, payload.due_date)
    order = _get_order_or_404(db, payload.order_id)

    rows = (
        db.query(PurchaseResult, OrderItem, Product)
        .join(SupplierAllocation, SupplierAllocation.id == PurchaseResult.allocation_id)
        .join(OrderItem, OrderItem.id == SupplierAllocation.order_item_id)
        .join(Product, Product.id == OrderItem.product_id)
        .filter(OrderItem.order_id == order.id)
        .filter(PurchaseResult.id.in_(payload.purchase_result_ids))
        .order_by(PurchaseResult.id.asc())
        .all()
    )
    if not rows:
        raise HTTPException(status_code=422, detail={"code": "PURCHASE_RESULTS_NOT_FOUND", "message": "no target purchase results found"})

    target_ids = [pr.id for pr, _, _ in rows]

    # idempotent: skip purchase results already marked as invoiced
    rows_to_create = [triple for triple in rows if triple[0].invoice_qty is None]
    if not rows_to_create:
        # keep existing contract: duplicated generation request returns 409
        raise HTTPException(status_code=409, detail={"code": "DRAFT_ALREADY_GENERATED", "message": "all target purchase results already invoiced"})

    invoice = Invoice(
        invoice_no=f"pending-{datetime.now().timestamp()}-{order.id}",
        customer_id=order.customer_id,
        tracking_no=order.tracking_no,
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
    _assign_invoice_header_numbers(db, invoice, order)

    settings = get_system_settings_or_404(db)
    subtotal = Decimal("0")
    tax_total = Decimal("0")
    for pr, item, product in rows_to_create:
        billable_qty = Decimal(str(pr.invoice_qty if pr.invoice_qty is not None else pr.purchased_qty))
        purchase_unit_cost = Decimal(str(pr.final_unit_cost if pr.final_unit_cost is not None else pr.unit_cost)) if (pr.final_unit_cost is not None or pr.unit_cost is not None) else None
        sales_unit_price, _ = _compute_auto_sales_unit_price(purchase_unit_cost)
        hkd_purchase_unit_cost = compute_hkd_purchase_unit_cost(
            jpy_purchase_unit_cost=purchase_unit_cost,
            freight_weight=(Decimal(str(product.freight_weight)) if product.freight_weight is not None else None),
            settings=settings,
        )

        line_amount = _amount(billable_qty * sales_unit_price)
        line_tax = Decimal("0")

        subtotal += line_amount
        tax_total += line_tax

        invoice_item = InvoiceItem(
            invoice_id=invoice.id,
            order_item_id=item.id,
            billable_qty=float(billable_qty),
            billable_uom=pr.purchased_uom,
            invoice_line_status="uninvoiced",
            sales_unit_price=float(sales_unit_price),
            unit_cost_basis=(float(hkd_purchase_unit_cost) if hkd_purchase_unit_cost is not None else None),
            source_purchase_unit_cost_jpy=float(purchase_unit_cost) if purchase_unit_cost is not None else None,
            line_amount=float(line_amount),
            tax_amount=float(line_tax),
        )
        db.add(invoice_item)
        db.flush()
        ensure_invoice_item_number(db, invoice, invoice_item)
        pr.invoice_qty = float(billable_qty)

    invoice.subtotal = float(_amount(subtotal))
    invoice.tax_total = float(_amount(tax_total))
    invoice.grand_total = float(_amount(subtotal + tax_total))

    write_audit_log(
        db,
        entity_type="invoice",
        entity_id=invoice.id,
        action=AuditAction.CREATE,
        after={
            "status": invoice.status.value,
            "is_locked": invoice.is_locked,
            "subtotal": float(invoice.subtotal),
            "tax_total": float(invoice.tax_total),
            "grand_total": float(invoice.grand_total),
            "source": "purchase_results",
            "source_order_id": order.id,
            "generated_item_count": len(rows_to_create),
            "target_purchase_result_ids": target_ids,
        },
    )
    db.commit()

    return InvoiceDraftGenerateResult(
        invoice_id=invoice.id,
        created_count=len(rows_to_create),
        target_purchase_result_ids=target_ids,
        idempotent_hit=False,
    )


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
    result = _finalize_invoice_row(db, row)
    db.commit()
    return result


@router.post(
    "/uuid/{invoice_uuid}/finalize",
    response_model=InvoiceFinalizeResponse,
    responses={
        **INVOICE_COMMON_ERROR_RESPONSES,
        404: {"model": ApiErrorResponse, "description": "Not Found"},
        409: {"model": ApiErrorResponse, "description": "Conflict"},
    },
)
def finalize_invoice_by_uuid(invoice_uuid: str, db: Session = Depends(get_db)) -> InvoiceFinalizeResponse:
    row = _get_invoice_by_uuid_or_404(db, invoice_uuid)
    result = _finalize_invoice_row(db, row)
    db.commit()
    return result


@router.post(
    "/finalize-batch",
    response_model=InvoiceBatchFinalizeResponse,
    responses={
        **INVOICE_COMMON_ERROR_RESPONSES,
        409: {"model": ApiErrorResponse, "description": "Conflict"},
    },
)
def finalize_invoices_batch(payload: InvoiceBatchFinalizeRequest, db: Session = Depends(get_db)) -> InvoiceBatchFinalizeResponse:
    results: list[InvoiceBatchFinalizeResult] = []
    seen: set[int] = set()

    for invoice_id in payload.invoice_ids:
        if invoice_id in seen:
            continue
        seen.add(invoice_id)

        savepoint = db.begin_nested()
        try:
            row = _get_invoice_or_404(db, invoice_id)
            finalized = _finalize_invoice_row(db, row, reason_code="batch_finalize")
            savepoint.commit()
            results.append(
                InvoiceBatchFinalizeResult(
                    invoice_id=finalized.invoice_id,
                    ok=True,
                    status=finalized.status,
                    is_locked=finalized.is_locked,
                )
            )
        except HTTPException as exc:
            savepoint.rollback()
            detail = exc.detail if isinstance(exc.detail, dict) else {}
            results.append(
                InvoiceBatchFinalizeResult(
                    invoice_id=invoice_id,
                    ok=False,
                    reason_code=detail.get("code", "BATCH_FINALIZE_FAILED"),
                    message=detail.get("message", "batch finalize failed"),
                )
            )

    db.commit()
    success_count = sum(1 for result in results if result.ok)
    failure_count = len(results) - success_count
    return InvoiceBatchFinalizeResponse(
        success_count=success_count,
        failure_count=failure_count,
        results=results,
    )


@router.post(
    "/{invoice_id}/recalculate-draft-costs",
    response_model=InvoiceDraftRecalculateResponse,
    responses={
        404: {"model": ApiErrorResponse, "description": "Not Found"},
        409: {"model": ApiErrorResponse, "description": "Conflict"},
        422: {"model": ApiErrorResponse, "description": "Validation Error"},
    },
)
def recalculate_draft_costs(invoice_id: int, db: Session = Depends(get_db)) -> InvoiceDraftRecalculateResponse:
    invoice = _get_invoice_or_404(db, invoice_id)
    if invoice.status != InvoiceStatus.draft:
        raise HTTPException(status_code=409, detail={"code": "INVOICE_NOT_DRAFT", "message": "invoice is not draft"})

    before = {
        "subtotal": float(invoice.subtotal),
        "tax_total": float(invoice.tax_total),
        "grand_total": float(invoice.grand_total),
    }
    recalculated_count = _recalculate_draft_invoice_costs(db, invoice)
    db.flush()
    write_audit_log(
        db,
        entity_type="invoice",
        entity_id=invoice.id,
        action=AuditAction.UPDATE,
        reason_code="recalculate_draft_costs",
        before=before,
        after={
            "recalculated_count": recalculated_count,
            "subtotal": float(invoice.subtotal),
            "tax_total": float(invoice.tax_total),
            "grand_total": float(invoice.grand_total),
        },
    )
    db.commit()
    return InvoiceDraftRecalculateResponse(
        invoice_id=invoice.id,
        recalculated_count=recalculated_count,
        subtotal=float(invoice.subtotal),
        tax_total=float(invoice.tax_total),
        grand_total=float(invoice.grand_total),
    )


@router.post(
    "/uuid/{invoice_uuid}/recalculate-draft-costs",
    response_model=InvoiceDraftRecalculateResponse,
    responses={
        404: {"model": ApiErrorResponse, "description": "Not Found"},
        409: {"model": ApiErrorResponse, "description": "Conflict"},
        422: {"model": ApiErrorResponse, "description": "Validation Error"},
    },
)
def recalculate_draft_costs_by_uuid(invoice_uuid: str, db: Session = Depends(get_db)) -> InvoiceDraftRecalculateResponse:
    invoice = _get_invoice_by_uuid_or_404(db, invoice_uuid)
    if invoice.status != InvoiceStatus.draft:
        raise HTTPException(status_code=409, detail={"code": "INVOICE_NOT_DRAFT", "message": "invoice is not draft"})

    before = {
        "subtotal": float(invoice.subtotal),
        "tax_total": float(invoice.tax_total),
        "grand_total": float(invoice.grand_total),
    }
    recalculated_count = _recalculate_draft_invoice_costs(db, invoice)
    db.flush()
    write_audit_log(
        db,
        entity_type="invoice",
        entity_id=invoice.id,
        action=AuditAction.UPDATE,
        reason_code="recalculate_draft_costs",
        before=before,
        after={
            "recalculated_count": recalculated_count,
            "subtotal": float(invoice.subtotal),
            "tax_total": float(invoice.tax_total),
            "grand_total": float(invoice.grand_total),
        },
    )
    db.commit()
    return InvoiceDraftRecalculateResponse(
        invoice_id=invoice.id,
        recalculated_count=recalculated_count,
        subtotal=float(invoice.subtotal),
        tax_total=float(invoice.tax_total),
        grand_total=float(invoice.grand_total),
    )


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
    if row.invoice_draft_no is not None:
        row.invoice_no = row.invoice_draft_no
    db.flush()
    _sync_order_statuses_for_invoice(db, row)
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
    "/uuid/{invoice_uuid}/reset-to-draft",
    response_model=InvoiceResetResponse,
    responses={
        **INVOICE_COMMON_ERROR_RESPONSES,
        404: {"model": ApiErrorResponse, "description": "Not Found"},
        409: {"model": ApiErrorResponse, "description": "Conflict"},
    },
)
def reset_to_draft_by_uuid(invoice_uuid: str, payload: InvoiceResetRequest, db: Session = Depends(get_db)) -> InvoiceResetResponse:
    row = _get_invoice_by_uuid_or_404(db, invoice_uuid)
    if row.status != InvoiceStatus.finalized:
        raise HTTPException(status_code=409, detail={"code": "INVOICE_NOT_FINALIZED", "message": "invoice is not finalized"})

    before = {"status": row.status.value, "is_locked": row.is_locked}
    row.status = InvoiceStatus.draft
    row.is_locked = False
    if row.invoice_draft_no is not None:
        row.invoice_no = row.invoice_draft_no
    db.flush()
    _sync_order_statuses_for_invoice(db, row)
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


@router.post(
    "/uuid/{invoice_uuid}/unlock",
    response_model=InvoiceUnlockResponse,
    responses={
        **INVOICE_COMMON_ERROR_RESPONSES,
        404: {"model": ApiErrorResponse, "description": "Not Found"},
        409: {"model": ApiErrorResponse, "description": "Conflict"},
    },
)
def unlock_invoice_by_uuid(invoice_uuid: str, payload: InvoiceUnlockRequest, db: Session = Depends(get_db)) -> InvoiceUnlockResponse:
    row = _get_invoice_by_uuid_or_404(db, invoice_uuid)
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
