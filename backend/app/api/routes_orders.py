from datetime import UTC, datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from io import BytesIO
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from reportlab.lib.pagesizes import portrait
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from sqlalchemy.orm import Session

from app.core.audit import AuditAction, write_audit_log
from app.db.session import get_db
from app.models.entities import Customer, LineStatus, Order, OrderItem, OrderStatus, PricingBasis, Product
from app.schemas.common import ApiErrorResponse
from app.schemas.order import (
    OrderBulkCancelRequest,
    OrderBulkCancelResponse,
    OrderBulkTransitionRequest,
    OrderBulkTransitionResponse,
    OrderCreateRequest,
    OrderUpdateRequest,
    OrderItemCreateRequest,
    OrderItemResponse,
    OrderItemsBulkCreateRequest,
    OrderItemsBulkCreateResponse,
    OrderItemLabelPdfRequest,
    OrderItemUpdateRequest,
    OrderResponse,
)

router = APIRouter(prefix="/api/v1/orders", tags=["orders"])

HK_TZ = ZoneInfo("Asia/Hong_Kong")


def _now_hk() -> datetime:
    return datetime.now(HK_TZ)


def _default_delivery_date_by_hk_time(now_hk: datetime) -> datetime.date:
    # 00:00-15:59 => same day, 16:00-23:59 => next day
    if now_hk.hour >= 16:
        return (now_hk + timedelta(days=1)).date()
    return now_hk.date()


ORDER_COMMON_ERROR_RESPONSES = {
    422: {"model": ApiErrorResponse, "description": "Validation Error"},
}


LABEL_PAGE_WIDTH_PT = 255.12  # 90mm
LABEL_PAGE_HEIGHT_PT = 368.50  # 130mm


def _pick_label_font() -> str:
    candidates = [
        ("NotoSansCJKjp", Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")),
        ("NotoSansCJKjp", Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc")),
        ("IPAexGothic", Path("/usr/share/fonts/truetype/ipaexg/ipaexg.ttf")),
        ("IPAexGothic", Path("/usr/share/fonts/ipaexfont-gothic/ipaexg.ttf")),
    ]
    for name, path in candidates:
        if not path.exists():
            continue
        try:
            if name not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(name, str(path), subfontIndex=0))
            return name
        except Exception:
            continue

    # Fallback (CJK capable but not embedded)
    fallback = "HeiseiKakuGo-W5"
    if fallback not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(UnicodeCIDFont(fallback))
    return fallback


def _truncate_with_ellipsis(c: canvas.Canvas, text: str, font: str, size: float, max_w: float) -> str:
    if c.stringWidth(text, font, size) <= max_w:
        return text
    s = text
    while s and c.stringWidth(s + "...", font, size) > max_w:
        s = s[:-1]
    return (s + "...") if s else "..."


def _wrap_text(c: canvas.Canvas, text: str, font: str, size: float, max_w: float, max_lines: int) -> list[str]:
    lines: list[str] = []
    rest = text
    for _ in range(max_lines):
        if not rest:
            break
        cur = rest
        while cur and c.stringWidth(cur, font, size) > max_w:
            cur = cur[:-1]
        if not cur:
            break
        lines.append(cur)
        rest = rest[len(cur):]
    if rest and lines:
        lines[-1] = _truncate_with_ellipsis(c, lines[-1] + rest, font, size, max_w)
    return lines or [""]


def _build_label_pdf(pages: list[dict[str, str]]) -> bytes:
    mm = 72 / 25.4
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=portrait((LABEL_PAGE_WIDTH_PT, LABEL_PAGE_HEIGHT_PT)), pageCompression=1)
    font = _pick_label_font()

    for p in pages:
        # blocks
        c.setLineWidth(0.85)
        c.rect(4 * mm, LABEL_PAGE_HEIGHT_PT - (4 + 36) * mm, 82 * mm, 36 * mm)
        c.rect(4 * mm, LABEL_PAGE_HEIGHT_PT - (42 + 34) * mm, 82 * mm, 34 * mm)
        c.rect(4 * mm, LABEL_PAGE_HEIGHT_PT - (78 + 48) * mm, 82 * mm, 48 * mm)
        c.line(4 * mm, LABEL_PAGE_HEIGHT_PT - 60 * mm, 86 * mm, LABEL_PAGE_HEIGHT_PT - 60 * mm)

        # header
        c.setFont(font, 7)
        c.drawString(6 * mm, LABEL_PAGE_HEIGHT_PT - 7 * mm, "取引先")
        c.setFont(font, 10)
        c.drawString(20 * mm, LABEL_PAGE_HEIGHT_PT - 7 * mm, _truncate_with_ellipsis(c, p["customer"], font, 10, 64 * mm))

        c.setFont(font, 7)
        c.drawString(6 * mm, LABEL_PAGE_HEIGHT_PT - 17 * mm, "商品名")
        name_size = 12
        lines = _wrap_text(c, p["product"], font, name_size, 64 * mm, 2)
        if len(lines) == 2 and c.stringWidth(lines[1], font, 12) > 64 * mm:
            name_size = 9
            lines = _wrap_text(c, p["product"], font, name_size, 64 * mm, 2)
        c.setFont(font, name_size)
        c.drawString(20 * mm, LABEL_PAGE_HEIGHT_PT - 17 * mm, lines[0])
        if len(lines) > 1:
            c.drawString(20 * mm, LABEL_PAGE_HEIGHT_PT - 23 * mm, lines[1])

        # quantity area
        c.setFont(font, 7)
        c.drawString(6 * mm, LABEL_PAGE_HEIGHT_PT - 46 * mm, "数量")
        c.drawString(50 * mm, LABEL_PAGE_HEIGHT_PT - 46 * mm, "単位")
        c.setFont(font, 18)
        qty = p["qty"]
        c.drawRightString(46 * mm, LABEL_PAGE_HEIGHT_PT - 45 * mm, qty)
        c.setFont(font, 12)
        c.drawString(62 * mm, LABEL_PAGE_HEIGHT_PT - 45 * mm, _truncate_with_ellipsis(c, p["uom"], font, 12, 22 * mm))

        c.setFont(font, 7)
        c.drawString(6 * mm, LABEL_PAGE_HEIGHT_PT - 62 * mm, "日付")
        c.setFont(font, 10)
        c.drawString(18 * mm, LABEL_PAGE_HEIGHT_PT - 61 * mm, p["date"])

        # footer
        c.setFont(font, 9)
        c.drawString(6 * mm, LABEL_PAGE_HEIGHT_PT - 82 * mm, "注文番号")
        c.drawString(24 * mm, LABEL_PAGE_HEIGHT_PT - 82 * mm, _truncate_with_ellipsis(c, p["order_no"], font, 9, 60 * mm))
        c.drawString(6 * mm, LABEL_PAGE_HEIGHT_PT - 91 * mm, "明細ID")
        c.drawString(24 * mm, LABEL_PAGE_HEIGHT_PT - 91 * mm, p["item_id"])

        c.setFont(font, 8)
        c.drawString(6 * mm, LABEL_PAGE_HEIGHT_PT - 100 * mm, "備考")
        note_lines = _wrap_text(c, p["note"], font, 8, 78 * mm, 2)
        c.drawString(6 * mm, LABEL_PAGE_HEIGHT_PT - 106 * mm, note_lines[0])
        if len(note_lines) > 1:
            c.drawString(6 * mm, LABEL_PAGE_HEIGHT_PT - 112 * mm, note_lines[1])

        c.showPage()

    c.save()
    return buf.getvalue()


def _stale_cutoff_delivery_date(now_hk: datetime) -> datetime.date:
    return _default_delivery_date_by_hk_time(now_hk)


@router.get("", response_model=list[OrderResponse])
def list_orders(
    stale_delivery_only: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> list[OrderResponse]:
    query = db.query(Order)
    if stale_delivery_only:
        cutoff = _stale_cutoff_delivery_date(_now_hk())
        query = query.filter(Order.delivery_date < cutoff, Order.status.in_([OrderStatus.new, OrderStatus.confirmed, OrderStatus.allocated]))

    rows = query.order_by(Order.id.desc()).all()
    return [OrderResponse.model_validate(r) for r in rows]


@router.get(
    "/{order_id}",
    response_model=OrderResponse,
    responses={**ORDER_COMMON_ERROR_RESPONSES, 404: {"model": ApiErrorResponse, "description": "Not Found"}},
)
def get_order(order_id: int, db: Session = Depends(get_db)) -> OrderResponse:
    row = db.query(Order).filter(Order.id == order_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "ORDER_NOT_FOUND", "message": "order not found"})
    return OrderResponse.model_validate(row)


@router.patch(
    "/{order_id}",
    response_model=OrderResponse,
    responses={
        **ORDER_COMMON_ERROR_RESPONSES,
        404: {"model": ApiErrorResponse, "description": "Not Found"},
    },
)
def update_order(order_id: int, payload: OrderUpdateRequest, db: Session = Depends(get_db)) -> OrderResponse:
    row = db.query(Order).filter(Order.id == order_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "ORDER_NOT_FOUND", "message": "order not found"})

    if payload.customer_id is not None:
        customer = db.query(Customer).filter(Customer.id == payload.customer_id).first()
        if customer is None:
            raise HTTPException(status_code=404, detail={"code": "CUSTOMER_NOT_FOUND", "message": "customer not found"})
        row.customer_id = payload.customer_id

    if payload.delivery_date is not None:
        row.delivery_date = payload.delivery_date

    if payload.shipped_date is not None or "shipped_date" in payload.model_fields_set:
        row.shipped_date = payload.shipped_date

    if payload.note is not None or "note" in payload.model_fields_set:
        row.note = payload.note

    row.updated_by = "system_api"
    db.flush()
    write_audit_log(db, entity_type="order", entity_id=row.id, action=AuditAction.UPDATE)
    db.commit()
    db.refresh(row)
    return OrderResponse.model_validate(row)


_TRANSITION_RULES: dict[tuple[OrderStatus, OrderStatus], tuple[LineStatus, LineStatus]] = {
    (OrderStatus.confirmed, OrderStatus.allocated): (LineStatus.open, LineStatus.allocated),
    (OrderStatus.allocated, OrderStatus.purchased): (LineStatus.allocated, LineStatus.purchased),
    (OrderStatus.purchased, OrderStatus.shipped): (LineStatus.purchased, LineStatus.shipped),
    (OrderStatus.shipped, OrderStatus.invoiced): (LineStatus.shipped, LineStatus.invoiced),
}


@router.post(
    "/{order_id}/bulk-transition",
    response_model=OrderBulkTransitionResponse,
    responses={
        **ORDER_COMMON_ERROR_RESPONSES,
        404: {"model": ApiErrorResponse, "description": "Not Found"},
        409: {"model": ApiErrorResponse, "description": "Conflict"},
    },
)
def bulk_transition_order(order_id: int, payload: OrderBulkTransitionRequest, db: Session = Depends(get_db)) -> OrderBulkTransitionResponse:
    order = db.query(Order).filter(Order.id == order_id).first()
    if order is None:
        raise HTTPException(status_code=404, detail={"code": "ORDER_NOT_FOUND", "message": "order not found"})

    if payload.from_status == payload.to_status:
        raise HTTPException(status_code=422, detail={"code": "INVALID_TRANSITION_PAIR", "message": "from_status and to_status must differ"})

    key = (payload.from_status, payload.to_status)
    if key not in _TRANSITION_RULES:
        raise HTTPException(status_code=422, detail={"code": "INVALID_TRANSITION_PAIR", "message": "invalid transition pair"})

    if order.status != payload.from_status:
        raise HTTPException(status_code=409, detail={"code": "ORDER_STATUS_MISMATCH", "message": "order status mismatch"})

    from_line, to_line = _TRANSITION_RULES[key]
    all_lines = db.query(OrderItem).filter(OrderItem.order_id == order_id).all()
    if not all_lines:
        raise HTTPException(status_code=409, detail={"code": "STATUS_NO_TARGET_LINES", "message": "no eligible lines"})

    invalid_lines = [line for line in all_lines if line.line_status != from_line]
    if invalid_lines:
        raise HTTPException(
            status_code=409,
            detail={"code": "LINE_STATUS_MISMATCH", "message": "all order lines must match from_status before transition"},
        )

    before = {
        "order_status": order.status.value,
        "line_status": from_line.value,
        "line_count": len(all_lines),
    }

    for line in all_lines:
        line.line_status = to_line

    order.status = payload.to_status
    order.updated_by = "system_api"
    db.flush()
    write_audit_log(
        db,
        entity_type="order",
        entity_id=order.id,
        action=AuditAction.BULK_TRANSITION,
        before=before,
        after={"order_status": order.status.value, "line_status": to_line.value, "line_count": len(all_lines)},
    )
    db.commit()

    return OrderBulkTransitionResponse(order_id=order.id, updated_lines=len(all_lines), updated_order_status=order.status)


@router.post(
    "/bulk-cancel",
    response_model=OrderBulkCancelResponse,
    responses={
        **ORDER_COMMON_ERROR_RESPONSES,
        409: {"model": ApiErrorResponse, "description": "Conflict"},
    },
)
def bulk_cancel_orders(payload: OrderBulkCancelRequest, db: Session = Depends(get_db)) -> OrderBulkCancelResponse:
    cancellable_statuses = {OrderStatus.new, OrderStatus.confirmed, OrderStatus.allocated}
    terminal_statuses = {OrderStatus.shipped, OrderStatus.invoiced, OrderStatus.cancelled}

    succeeded = 0
    errors = []

    for order_id in payload.order_ids:
        order = db.query(Order).filter(Order.id == order_id).first()
        if order is None:
            errors.append({"order_id": order_id, "code": "ORDER_NOT_FOUND", "message": "order not found"})
            continue

        if order.status in terminal_statuses:
            errors.append({"order_id": order_id, "code": "ORDER_CANCEL_CONFLICT", "message": f"cannot cancel from status={order.status.value}"})
            continue

        if order.status not in cancellable_statuses:
            errors.append({"order_id": order_id, "code": "ORDER_CANCEL_CONFLICT", "message": f"cannot cancel from status={order.status.value}"})
            continue

        lines = db.query(OrderItem).filter(OrderItem.order_id == order.id).all()
        for line in lines:
            line.line_status = LineStatus.cancelled

        order.status = OrderStatus.cancelled
        if payload.note:
            order.note = payload.note
        order.updated_by = "system_api"
        db.flush()
        write_audit_log(db, entity_type="order", entity_id=order.id, action=AuditAction.CANCEL, reason_code=payload.cancel_reason_code)
        succeeded += 1

    db.commit()
    failed = len(payload.order_ids) - succeeded

    if succeeded == 0 and failed > 0:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "ORDER_BULK_CANCEL_CONFLICT",
                "message": "all target orders failed to cancel",
                "details": errors,
            },
        )

    return OrderBulkCancelResponse(total=len(payload.order_ids), succeeded=succeeded, failed=failed, errors=errors)


@router.post(
    "/item-labels/pdf",
    responses={
        **ORDER_COMMON_ERROR_RESPONSES,
        404: {"model": ApiErrorResponse, "description": "Not Found"},
        200: {"content": {"application/pdf": {}}},
    },
)
def generate_order_item_labels_pdf(payload: OrderItemLabelPdfRequest, db: Session = Depends(get_db)) -> Response:
    order_items = db.query(OrderItem, Order, Customer, Product).join(Order, Order.id == OrderItem.order_id).join(Customer, Customer.id == Order.customer_id).join(Product, Product.id == OrderItem.product_id).filter(OrderItem.id.in_(payload.order_item_ids)).all()
    by_id = {oi.id: (oi, o, c, p) for oi, o, c, p in order_items}

    missing = [oid for oid in payload.order_item_ids if oid not in by_id]
    if missing:
        raise HTTPException(status_code=404, detail={"code": "ORDER_ITEM_NOT_FOUND", "message": f"order item not found: {missing[0]}"})

    pages: list[dict[str, str]] = []
    for oid in payload.order_item_ids:
        oi, order, customer, product = by_id[oid]
        qty = f"{float(oi.ordered_qty):.3f}".rstrip("0").rstrip(".")
        pages.append(
            {
                "customer": customer.name or "-",
                "product": product.name or "-",
                "qty": qty,
                "uom": product.order_uom or "-",
                "date": str(order.shipped_date or order.delivery_date),
                "order_no": order.order_no or "-",
                "item_id": str(oi.id),
                "note": (oi.note or "-")[:200],
            }
        )

    pdf_bytes = _build_label_pdf(pages)
    return Response(content=pdf_bytes, media_type="application/pdf")


@router.post(
    "",
    response_model=OrderResponse,
    status_code=201,
    responses={
        **ORDER_COMMON_ERROR_RESPONSES,
        404: {"model": ApiErrorResponse, "description": "Not Found"},
        409: {"model": ApiErrorResponse, "description": "Conflict"},
    },
)
def create_order(payload: OrderCreateRequest, db: Session = Depends(get_db)) -> OrderResponse:
    customer = db.query(Customer).filter(Customer.id == payload.customer_id).first()
    if customer is None:
        raise HTTPException(status_code=404, detail={"code": "CUSTOMER_NOT_FOUND", "message": "customer not found"})

    row = None
    for _ in range(5):
        generated_order_no = f"ORD-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6].upper()}"
        if db.query(Order).filter(Order.order_no == generated_order_no).first() is not None:
            continue

        now_hk = _now_hk()
        row = Order(
            order_no=generated_order_no,
            customer_id=payload.customer_id,
            order_datetime=datetime.now(UTC),
            delivery_date=(payload.delivery_date or _default_delivery_date_by_hk_time(now_hk)),
            shipped_date=payload.shipped_date,
            status=OrderStatus.new,
            note=payload.note,
            created_by="system_api",
            updated_by="system_api",
        )
        db.add(row)
        db.flush()
        break

    if row is None:
        raise HTTPException(status_code=409, detail={"code": "ORDER_NO_GENERATION_FAILED", "message": "failed to generate order_no"})

    write_audit_log(db, entity_type="order", entity_id=row.id, action=AuditAction.CREATE)
    db.commit()
    db.refresh(row)
    return OrderResponse.model_validate(row)


def _validate_order_item_pricing(payload: OrderItemCreateRequest | OrderItemUpdateRequest) -> None:
    pricing_basis = payload.pricing_basis
    if pricing_basis == PricingBasis.uom_count:
        if payload.unit_price_uom_count is None:
            raise HTTPException(status_code=422, detail={"code": "VALIDATION_FAILED", "message": "unit_price_uom_count is required"})
    if pricing_basis == PricingBasis.uom_kg:
        if payload.unit_price_uom_kg is None:
            raise HTTPException(status_code=422, detail={"code": "VALIDATION_FAILED", "message": "unit_price_uom_kg is required"})


@router.get("/{order_id}/items", response_model=list[OrderItemResponse])
def list_order_items(order_id: int, db: Session = Depends(get_db)) -> list[OrderItemResponse]:
    order = db.query(Order).filter(Order.id == order_id).first()
    if order is None:
        raise HTTPException(status_code=404, detail={"code": "ORDER_NOT_FOUND", "message": "order not found"})

    rows = db.query(OrderItem).filter(OrderItem.order_id == order_id).order_by(OrderItem.id.asc()).all()
    return [OrderItemResponse.model_validate(r) for r in rows]


@router.post("/{order_id}/items", response_model=OrderItemResponse, status_code=201)
def create_order_item(order_id: int, payload: OrderItemCreateRequest, db: Session = Depends(get_db)) -> OrderItemResponse:
    order = db.query(Order).filter(Order.id == order_id).first()
    if order is None:
        raise HTTPException(status_code=404, detail={"code": "ORDER_NOT_FOUND", "message": "order not found"})

    product = db.query(Product).filter(Product.id == payload.product_id).first()
    if product is None:
        raise HTTPException(status_code=404, detail={"code": "PRODUCT_NOT_FOUND", "message": "product not found"})

    _validate_order_item_pricing(payload)

    row = OrderItem(
        order_id=order_id,
        product_id=payload.product_id,
        ordered_qty=payload.ordered_qty,
        order_uom_type=payload.order_uom_type,
        estimated_weight_kg=payload.estimated_weight_kg,
        target_price=payload.target_price,
        price_ceiling=payload.price_ceiling,
        stockout_policy=payload.stockout_policy,
        pricing_basis=payload.pricing_basis,
        unit_price_uom_count=payload.unit_price_uom_count,
        unit_price_uom_kg=payload.unit_price_uom_kg,
        note=payload.note,
        comment=payload.comment,
    )
    db.add(row)
    db.flush()
    order.updated_by = "system_api"
    db.commit()
    db.refresh(row)
    return OrderItemResponse.model_validate(row)


@router.post("/{order_id}/items/bulk", response_model=OrderItemsBulkCreateResponse)
def bulk_create_order_items(order_id: int, payload: OrderItemsBulkCreateRequest, db: Session = Depends(get_db)) -> OrderItemsBulkCreateResponse:
    order = db.query(Order).filter(Order.id == order_id).first()
    if order is None:
        raise HTTPException(status_code=404, detail={"code": "ORDER_NOT_FOUND", "message": "order not found"})

    success = 0
    errors: list[dict] = []
    for idx, item in enumerate(payload.items):
        product = db.query(Product).filter(Product.id == item.product_id).first()
        if product is None:
            errors.append({"index": idx, "field": "product_id", "code": "PRODUCT_NOT_FOUND", "message": "product not found"})
            continue
        try:
            _validate_order_item_pricing(item)
        except HTTPException as e:
            errors.append({"index": idx, "field": "pricing_basis", "code": e.detail.get("code", "VALIDATION_FAILED"), "message": e.detail.get("message", "validation failed")})
            continue

        db.add(
            OrderItem(
                order_id=order_id,
                product_id=item.product_id,
                ordered_qty=item.ordered_qty,
                order_uom_type=item.order_uom_type,
                estimated_weight_kg=item.estimated_weight_kg,
                target_price=item.target_price,
                price_ceiling=item.price_ceiling,
                stockout_policy=item.stockout_policy,
                pricing_basis=item.pricing_basis,
                unit_price_uom_count=item.unit_price_uom_count,
                unit_price_uom_kg=item.unit_price_uom_kg,
                note=item.note,
                comment=item.comment,
            )
        )
        success += 1

    order.updated_by = "system_api"
    db.commit()
    return OrderItemsBulkCreateResponse(total=len(payload.items), success=success, failed=len(payload.items) - success, errors=errors)


@router.patch("/{order_id}/items/{item_id}", response_model=OrderItemResponse)
def update_order_item(order_id: int, item_id: int, payload: OrderItemUpdateRequest, db: Session = Depends(get_db)) -> OrderItemResponse:
    order = db.query(Order).filter(Order.id == order_id).first()
    if order is None:
        raise HTTPException(status_code=404, detail={"code": "ORDER_NOT_FOUND", "message": "order not found"})

    row = db.query(OrderItem).filter(OrderItem.id == item_id, OrderItem.order_id == order_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "RESOURCE_NOT_FOUND", "message": "order item not found"})

    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(row, k, v)

    if payload.pricing_basis is not None or payload.unit_price_uom_count is not None or payload.unit_price_uom_kg is not None:
        pb = payload.pricing_basis or row.pricing_basis
        temp = OrderItemUpdateRequest(pricing_basis=pb, unit_price_uom_count=row.unit_price_uom_count, unit_price_uom_kg=row.unit_price_uom_kg)
        _validate_order_item_pricing(temp)

    order.updated_by = "system_api"
    db.commit()
    db.refresh(row)
    return OrderItemResponse.model_validate(row)


@router.delete("/{order_id}/items/{item_id}", status_code=204)
def delete_order_item(order_id: int, item_id: int, db: Session = Depends(get_db)) -> None:
    order = db.query(Order).filter(Order.id == order_id).first()
    if order is None:
        raise HTTPException(status_code=404, detail={"code": "ORDER_NOT_FOUND", "message": "order not found"})

    row = db.query(OrderItem).filter(OrderItem.id == item_id, OrderItem.order_id == order_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "RESOURCE_NOT_FOUND", "message": "order item not found"})

    db.delete(row)
    order.updated_by = "system_api"
    db.commit()
    return None
