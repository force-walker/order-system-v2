from datetime import date
from io import BytesIO
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from reportlab.lib.pagesizes import portrait
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import Customer, Order, OrderItem, Product, Supplier, SupplierAllocation
from app.schemas.report import PurchaseConfirmationPdfRequest, ShippingReportRow, ShippingReportSortMode

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


def _pick_font() -> str:
    candidates = [
        ("NotoSansCJKjp", Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")),
        ("IPAexGothic", Path("/usr/share/fonts/truetype/ipaexg/ipaexg.ttf")),
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
    fallback = "HeiseiKakuGo-W5"
    if fallback not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(UnicodeCIDFont(fallback))
    return fallback


def _ellipsis(c: canvas.Canvas, text: str, font: str, size: float, width: float) -> str:
    if c.stringWidth(text, font, size) <= width:
        return text
    t = text
    while t and c.stringWidth(t + "...", font, size) > width:
        t = t[:-1]
    return (t + "...") if t else "..."


def _latest_allocation_subquery(db: Session):
    latest_id_sq = (
        db.query(
            SupplierAllocation.order_item_id.label("order_item_id"),
            func.max(SupplierAllocation.id).label("latest_id"),
        )
        .group_by(SupplierAllocation.order_item_id)
        .subquery()
    )

    return (
        db.query(
            SupplierAllocation.order_item_id.label("order_item_id"),
            SupplierAllocation.final_supplier_id.label("final_supplier_id"),
            SupplierAllocation.final_qty.label("final_qty"),
        )
        .join(
            latest_id_sq,
            (SupplierAllocation.order_item_id == latest_id_sq.c.order_item_id)
            & (SupplierAllocation.id == latest_id_sq.c.latest_id),
        )
        .subquery()
    )


@router.post(
    "/purchase-confirmation/pdf",
    responses={
        200: {"content": {"application/pdf": {}}},
        404: {"description": "Not Found"},
        422: {"description": "Validation Error"},
    },
)
def purchase_confirmation_pdf(payload: PurchaseConfirmationPdfRequest, db: Session = Depends(get_db)) -> Response:
    ids = payload.selected_ids
    if not ids:
        raise HTTPException(status_code=422, detail={"code": "VALIDATION_FAILED", "message": "selected_ids is required"})

    alloc = _latest_allocation_subquery(db)
    rows = (
        db.query(OrderItem, Order, Customer, Product, Supplier, alloc.c.final_qty)
        .join(Order, OrderItem.order_id == Order.id)
        .join(Customer, Order.customer_id == Customer.id)
        .join(Product, OrderItem.product_id == Product.id)
        .outerjoin(alloc, alloc.c.order_item_id == OrderItem.id)
        .outerjoin(Supplier, Supplier.id == alloc.c.final_supplier_id)
        .filter(OrderItem.id.in_(ids))
        .order_by(Product.name.desc(), OrderItem.id.desc())
        .all()
    )

    found_ids = {item.id for item, *_ in rows}
    missing = [x for x in ids if x not in found_ids]
    if missing:
        raise HTTPException(status_code=404, detail={"code": "ORDER_ITEM_NOT_FOUND", "message": f"order item not found: {missing[0]}"})

    if not rows:
        raise HTTPException(status_code=404, detail={"code": "ORDER_ITEMS_NOT_FOUND", "message": "order items not found"})

    A4_W, A4_H = portrait((595.27, 841.89))
    cbuf = BytesIO()
    c = canvas.Canvas(cbuf, pagesize=(A4_W, A4_H), pageCompression=1)
    font = _pick_font()
    headers = ["仕入先名", "得意先分類名", "得意先名", "商品名", "数量", "単位名", "備考1", "備考2", "単価"]
    col_w = [72, 36, 72, 108, 44, 44, 62, 62, 40]  # 得意先分類名を半分幅へ

    def header(y):
        x = 20
        for idx, (h, w) in enumerate(zip(headers, col_w)):
            c.rect(x, y - 14, w, 16)
            col_font_size = 4 if idx == 1 else 8  # 得意先分類名のみフォント半分
            c.setFont(font, col_font_size)
            c.drawString(x + 2, y - 10, _ellipsis(c, h, font, col_font_size, w - 4))
            x += w

    y = A4_H - 28
    header(y)
    y -= 18
    c.setFont(font, 8)

    for item, _order, customer, product, supplier, final_qty in rows:
        if y < 36:
            c.showPage()
            y = A4_H - 28
            header(y)
            y -= 18
            c.setFont(font, 8)
        vals = [
            supplier.name if supplier else "",
            customer.region or "",
            customer.name or "",
            product.name or "",
            (f"{float(final_qty):.3f}".rstrip("0").rstrip(".") if final_qty is not None else f"{float(item.ordered_qty):.3f}".rstrip("0").rstrip(".")),
            product.order_uom or "",
            (item.note or ""),
            (item.comment or ""),
            str(item.unit_price_uom_count or item.unit_price_uom_kg or ""),
        ]
        x = 20
        for idx, (v, w) in enumerate(zip(vals, col_w)):
            c.rect(x, y - 12, w, 14)
            col_font_size = 4 if idx == 1 else 8
            c.setFont(font, col_font_size)
            c.drawString(x + 2, y - 9, _ellipsis(c, str(v), font, col_font_size, w - 4))
            x += w
        y -= 14

    c.save()
    return Response(content=cbuf.getvalue(), media_type="application/pdf")


@router.get("/shipping", response_model=list[ShippingReportRow])
def shipping_report(
    shipped_date: date = Query(...),
    mode: ShippingReportSortMode = Query(default=ShippingReportSortMode.supplier_product),
    db: Session = Depends(get_db),
) -> list[ShippingReportRow]:
    alloc = _latest_allocation_subquery(db)

    query = (
        db.query(OrderItem, Order, Customer, Product, alloc.c.final_supplier_id, alloc.c.final_qty, Supplier)
        .join(Order, OrderItem.order_id == Order.id)
        .join(Customer, Order.customer_id == Customer.id)
        .join(Product, OrderItem.product_id == Product.id)
        .outerjoin(alloc, alloc.c.order_item_id == OrderItem.id)
        .outerjoin(Supplier, Supplier.id == alloc.c.final_supplier_id)
        .filter(OrderItem.shipped_date == shipped_date)
    )

    if mode == ShippingReportSortMode.supplier_product:
        query = query.order_by(Supplier.name.asc().nulls_last(), Product.name.asc(), Customer.name.asc(), OrderItem.id.asc())
    else:
        query = query.order_by(Customer.name.asc(), Supplier.name.asc().nulls_last(), Product.name.asc(), OrderItem.id.asc())

    rows = query.all()
    result: list[ShippingReportRow] = []
    for item, _order, customer, product, _supplier_id, final_qty, supplier in rows:
        qty = float(final_qty) if final_qty is not None else float(item.ordered_qty)
        result.append(
            ShippingReportRow(
                order_item_id=item.id,
                shipped_date=item.shipped_date,
                supplier_name=(supplier.name if supplier is not None else None),
                customer_name=customer.name,
                product_name=product.name,
                quantity=qty,
                unit=product.order_uom,
            )
        )

    return result
