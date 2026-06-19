from datetime import UTC, datetime, timedelta
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
from app.core.numbering import ensure_order_header_numbers, ensure_order_item_number
from app.db.session import get_db
from app.models.entities import Customer, LineStatus, Order, OrderItem, OrderStatus, PricingBasis, Product, Supplier, SupplierAllocation
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
    PurchaseConfirmationPdfRequest,
)

from collections import defaultdict

def _add_line_numbers(pages: list[dict[str, str]]) -> list[dict[str, str]]:
    totals = defaultdict(int)
    counters = defaultdict(int)

    for p in pages:
        totals[p.get("order_no", "")] += 1

    result = []
    for p in pages:
        order_no = p.get("order_no", "")
        counters[order_no] += 1

        row = dict(p)
        row["line_no"] = str(counters[order_no])
        row["line_total"] = str(totals[order_no])
        result.append(row)

    return result

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


def _wrap_text(c: canvas.Canvas, text: str, font: str, size: float, max_w: float, max_lines: int) -> tuple[list[str], bool]:
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
    overflow = bool(rest)
    if rest and lines:
        lines[-1] = _truncate_with_ellipsis(c, lines[-1] + rest, font, size, max_w)
    return (lines or [""], overflow)


def _build_label_pdf(pages: list[dict[str, str]]) -> bytes:
    mm = 72 / 25.4
    buf = BytesIO()

    c = canvas.Canvas(
        buf,
        pagesize=portrait((LABEL_PAGE_WIDTH_PT, LABEL_PAGE_HEIGHT_PT)),
        pageCompression=1,
    )
    font = _pick_label_font()

    required_keys = (
        "customer",
        "product",
        "qty",
        "uom",
        "date",
        "order_no",
        "note",
        "region",
        "line_no",
        "line_total",
    )

    def v(p: dict[str, str], key: str) -> str:
        return str(p.get(key, "") or "")

    for raw in pages:
        p = {k: v(raw, k) for k in required_keys}

        # optional guide blocks / outer layout
        # border/frame lines removed by request

        # --- positions based on PPTX right-label visual ---
        # y values are measured from top of label in mm.

        # date
        c.setFont(font, 10)
        c.drawString(
            10 * mm,
            LABEL_PAGE_HEIGHT_PT - 8 * mm,
            _truncate_with_ellipsis(c, p["date"], font, 10, 28 * mm),
        )

        # region (above customer)
        region_size = 18
        c.setFont(font, region_size)
        c.drawCentredString(
            45 * mm,
            LABEL_PAGE_HEIGHT_PT - 14 * mm,
            _truncate_with_ellipsis(c, (p["region"] or "-"), font, region_size, 70 * mm),
        )

        # customer
        customer_size = 14
        c.setFont(font, customer_size)
        c.drawCentredString(
            45 * mm,
            LABEL_PAGE_HEIGHT_PT - 23 * mm,
            _truncate_with_ellipsis(c, p["customer"], font, customer_size, 70 * mm),
        )
        # product, up to 2 lines (larger than customer)
        product_size = 22
        product_lines, overflow = _wrap_text(c, p["product"], font, product_size, 74 * mm, 2)
        if overflow:
            product_size = 18
            product_lines, _ = _wrap_text(c, p["product"], font, product_size, 74 * mm, 2)

        product_lines = product_lines or [""]

        c.setFont(font, product_size)
        if len(product_lines) == 1:
            c.drawCentredString(
                45 * mm,
                LABEL_PAGE_HEIGHT_PT - 42 * mm,
                product_lines[0],
            )
        else:
            c.drawCentredString(
                45 * mm,
                LABEL_PAGE_HEIGHT_PT - 40 * mm,
                product_lines[0],
            )
            c.drawCentredString(
                45 * mm,
                LABEL_PAGE_HEIGHT_PT - 47 * mm,
                product_lines[1],
            )

        # qty / uom
        c.setFont(font, 22)
        c.drawRightString(
            43 * mm,
            LABEL_PAGE_HEIGHT_PT - 60 * mm,
            p["qty"],
        )

        c.setFont(font, 18)
        c.drawString(
            46 * mm,
            LABEL_PAGE_HEIGHT_PT - 60 * mm,
            _truncate_with_ellipsis(c, p["uom"], font, 18, 36 * mm),
        )

        # note
        c.setFont(font, 10)
        note_lines, _ = _wrap_text(c, p["note"], font, 10, 74 * mm, 2)
        note_lines = note_lines or [""]

        c.drawString(
            10 * mm,
            LABEL_PAGE_HEIGHT_PT - 72 * mm,
            note_lines[0],
        )
        if len(note_lines) > 1:
            c.drawString(
                10 * mm,
                LABEL_PAGE_HEIGHT_PT - 78 * mm,
                note_lines[1],
            )

        # order no
        c.setFont(font, 8)
        c.drawString(10 * mm, LABEL_PAGE_HEIGHT_PT - 90 * mm, "受注No")

        c.setFont(font, 10)
        order_lines, _ = _wrap_text(c, p["order_no"], font, 10, 32 * mm, 3)
        order_lines = order_lines or [""]

        for i, line in enumerate(order_lines[:3]):
            c.drawString(
                10 * mm,
                LABEL_PAGE_HEIGHT_PT - (97 + i * 6) * mm,
                line,
            )

        # item id / line number
        # same-order detail line number / total
        c.setFont(font, 10)
        line_info = ""
        if p["line_no"] or p["line_total"]:
            line_info = f'{p["line_no"]}/{p["line_total"]}'

        c.drawRightString(
            82 * mm,
            LABEL_PAGE_HEIGHT_PT - 116 * mm,
            line_info,
        )


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
    "/{order_id}/purchase-confirmation.pdf",
    responses={
        **ORDER_COMMON_ERROR_RESPONSES,
        404: {"model": ApiErrorResponse, "description": "Not Found"},
        200: {"content": {"application/pdf": {}}},
    },
)
def generate_purchase_confirmation_pdf(order_id: int, payload: PurchaseConfirmationPdfRequest, db: Session = Depends(get_db)) -> Response:
    order = db.query(Order).filter(Order.id == order_id).first()
    if order is None:
        raise HTTPException(status_code=404, detail={"code": "ORDER_NOT_FOUND", "message": "order not found"})

    rows = (
        db.query(OrderItem, Customer, Product, Supplier)
        .join(Order, Order.id == OrderItem.order_id)
        .join(Customer, Customer.id == Order.customer_id)
        .join(Product, Product.id == OrderItem.product_id)
        .outerjoin(SupplierAllocation, SupplierAllocation.order_item_id == OrderItem.id)
        .outerjoin(Supplier, Supplier.id == SupplierAllocation.final_supplier_id)
        .filter(OrderItem.order_id == order_id)
        .order_by(Product.name.desc(), OrderItem.id.desc())
        .all()
    )

    if not rows:
        raise HTTPException(status_code=404, detail={"code": "ORDER_ITEMS_NOT_FOUND", "message": "order items not found"})

    A4_W, A4_H = portrait((595.27, 841.89))
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(A4_W, A4_H), pageCompression=1)
    font = _pick_label_font()
    headers = ["仕入先名", "得意先分類名", "得意先名", "商品名", "数量", "単位名", "備考1", "備考2", "単価"]
    col_w = [70, 70, 70, 110, 45, 45, 70, 70, 45]

    def draw_header(y: float):
        x = 24
        c.setFont(font, 9)
        for h, w in zip(headers, col_w):
            c.rect(x, y - 14, w, 16)
            c.drawString(x + 2, y - 10, h)
            x += w

    y = A4_H - 36
    draw_header(y)
    y -= 18
    c.setFont(font, 8)

    for item, customer, product, supplier in rows:
        if y < 40:
            c.showPage()
            y = A4_H - 36
            draw_header(y)
            y -= 18
            c.setFont(font, 8)

        vals = [
            supplier.name if supplier else "",
            customer.region or "",
            customer.name or "",
            product.name or "",
            f"{float(item.ordered_qty):.3f}".rstrip("0").rstrip("."),
            product.order_uom or "",
            (item.note or "")[:20],
            (item.comment or "")[:20],
            str(item.unit_price_uom_count or item.unit_price_uom_kg or ""),
        ]
        x = 24
        for v, w in zip(vals, col_w):
            c.rect(x, y - 12, w, 14)
            c.drawString(x + 2, y - 9, _truncate_with_ellipsis(c, v, font, 8, w - 4))
            x += w
        y -= 14

    c.save()
    return Response(content=buf.getvalue(), media_type="application/pdf")


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
                "region": (customer.region or "-")[:64],
            }
        )

    pages = _add_line_numbers(pages)
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

    now_hk = _now_hk()
    row = Order(
        order_no=f"pending-{datetime.now(UTC).timestamp()}",
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
    ensure_order_header_numbers(db, row, now_hk=now_hk)

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
    ensure_order_item_number(db, order, row)
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

        row = OrderItem(
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
        db.add(row)
        db.flush()
        ensure_order_item_number(db, order, row)
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
