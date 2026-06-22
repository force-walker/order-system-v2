from datetime import date
from io import BytesIO
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from sqlalchemy.orm import Session

from app.core.audit import AuditAction, write_audit_log
from app.core.deliveries import ensure_delivery_document
from app.db.session import get_db
from app.models.entities import Customer, Delivery, DeliveryItem, Invoice, InvoiceItem, Order, OrderItem, OrderStatus, Product
from app.schemas.common import ApiErrorResponse
from app.schemas.delivery import DeliveryBuildRequest, DeliveryItemResponse, DeliveryResponse
from app.schemas.invoice import InvoiceSummaryRow

router = APIRouter(prefix="/api/v1/deliveries", tags=["deliveries"])


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


def _get_delivery_or_404(db: Session, delivery_id: str) -> Delivery:
    row = db.query(Delivery).filter(Delivery.id == delivery_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "DELIVERY_NOT_FOUND", "message": "delivery not found"})
    return row


def _get_order_or_404(db: Session, order_id: str | int) -> Order:
    ident = str(order_id)
    row = db.query(Order).filter(Order.id == ident).first()
    if row is None and ident.isdigit():
        row = db.query(Order).filter(Order.legacy_id == int(ident)).first()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "ORDER_NOT_FOUND", "message": "order not found"})
    return row


def _assert_order_deliverable(order: Order) -> None:
    if order.status not in {OrderStatus.shipped, OrderStatus.invoiced}:
        raise HTTPException(status_code=409, detail={"code": "ORDER_NOT_SHIPPED", "message": "order is not shipped"})


def _delivery_invoice_rows(db: Session, delivery: Delivery) -> list[InvoiceSummaryRow]:
    rows = (
        db.query(Invoice, Customer)
        .join(Customer, Customer.id == Invoice.customer_id)
        .filter(
            (Invoice.delivery_no == delivery.delivery_no)
            | ((Invoice.delivery_no.is_(None)) & (Invoice.tracking_no == delivery.tracking_no))
        )
        .order_by(Invoice.created_at.desc())
        .all()
    )

    result: list[InvoiceSummaryRow] = []
    for invoice, customer in rows:
        item_count = db.query(InvoiceItem.id).filter(InvoiceItem.invoice_id == invoice.id).count()
        result.append(
            InvoiceSummaryRow(
                invoice_id=invoice.id,
                invoice_uuid=invoice.uuid,
                tracking_no=invoice.tracking_no,
                delivery_id=delivery.id,
                delivery_uuid=delivery.uuid,
                delivery_no=invoice.delivery_no or delivery.delivery_no,
                invoice_no=invoice.invoice_no,
                invoice_draft_no=invoice.invoice_draft_no,
                official_invoice_no=invoice.official_invoice_no,
                customer_name=customer.name,
                invoice_date=invoice.invoice_date,
                delivery_date=invoice.delivery_date,
                due_date=invoice.due_date,
                status=invoice.status,
                subtotal=float(invoice.subtotal),
                tax_total=float(invoice.tax_total),
                grand_total=float(invoice.grand_total),
                item_count=item_count,
            )
        )
    return result


@router.get("", response_model=list[DeliveryResponse])
def list_deliveries(
    order_id: str | None = Query(default=None),
    order_uuid: str | None = Query(default=None),
    shipped_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[DeliveryResponse]:
    query = db.query(Delivery)
    if order_id is not None:
        order = _get_order_or_404(db, order_id)
        query = query.filter(Delivery.order_id == order.id)
    if order_uuid is not None:
        order = _get_order_or_404(db, order_uuid)
        query = query.filter(Delivery.order_id == order.id)
    if shipped_date is not None:
        query = query.filter(Delivery.shipped_date == shipped_date)
    rows = query.order_by(Delivery.created_at.desc()).all()
    return [DeliveryResponse.model_validate(row) for row in rows]


@router.get(
    "/{delivery_id}",
    response_model=DeliveryResponse,
    responses={404: {"model": ApiErrorResponse, "description": "Not Found"}},
)
def get_delivery(delivery_id: str, db: Session = Depends(get_db)) -> DeliveryResponse:
    return DeliveryResponse.model_validate(_get_delivery_or_404(db, delivery_id))


@router.get(
    "/uuid/{delivery_uuid}",
    response_model=DeliveryResponse,
    responses={404: {"model": ApiErrorResponse, "description": "Not Found"}},
)
def get_delivery_by_uuid(delivery_uuid: str, db: Session = Depends(get_db)) -> DeliveryResponse:
    return DeliveryResponse.model_validate(_get_delivery_or_404(db, delivery_uuid))


@router.get(
    "/{delivery_id}/items",
    response_model=list[DeliveryItemResponse],
    responses={404: {"model": ApiErrorResponse, "description": "Not Found"}},
)
def list_delivery_items(delivery_id: str, db: Session = Depends(get_db)) -> list[DeliveryItemResponse]:
    delivery = _get_delivery_or_404(db, delivery_id)
    rows = db.query(DeliveryItem).filter(DeliveryItem.delivery_id == delivery.id).order_by(DeliveryItem.created_at.asc()).all()
    return [DeliveryItemResponse.model_validate(row) for row in rows]


@router.get(
    "/uuid/{delivery_uuid}/items",
    response_model=list[DeliveryItemResponse],
    responses={404: {"model": ApiErrorResponse, "description": "Not Found"}},
)
def list_delivery_items_by_uuid(delivery_uuid: str, db: Session = Depends(get_db)) -> list[DeliveryItemResponse]:
    delivery = _get_delivery_or_404(db, delivery_uuid)
    rows = db.query(DeliveryItem).filter(DeliveryItem.delivery_id == delivery.id).order_by(DeliveryItem.created_at.asc()).all()
    return [DeliveryItemResponse.model_validate(row) for row in rows]


@router.get(
    "/{delivery_id}/invoices",
    response_model=list[InvoiceSummaryRow],
    responses={404: {"model": ApiErrorResponse, "description": "Not Found"}},
)
def list_delivery_invoices(delivery_id: str, db: Session = Depends(get_db)) -> list[InvoiceSummaryRow]:
    delivery = _get_delivery_or_404(db, delivery_id)
    return _delivery_invoice_rows(db, delivery)


@router.get(
    "/uuid/{delivery_uuid}/invoices",
    response_model=list[InvoiceSummaryRow],
    responses={404: {"model": ApiErrorResponse, "description": "Not Found"}},
)
def list_delivery_invoices_by_uuid(delivery_uuid: str, db: Session = Depends(get_db)) -> list[InvoiceSummaryRow]:
    delivery = _get_delivery_or_404(db, delivery_uuid)
    return _delivery_invoice_rows(db, delivery)


@router.post(
    "/from-order",
    response_model=DeliveryResponse,
    responses={
        404: {"model": ApiErrorResponse, "description": "Not Found"},
        409: {"model": ApiErrorResponse, "description": "Conflict"},
        422: {"model": ApiErrorResponse, "description": "Validation Error"},
    },
)
def build_delivery_from_order(payload: DeliveryBuildRequest, db: Session = Depends(get_db)) -> DeliveryResponse:
    order = _get_order_or_404(db, payload.order_id)
    _assert_order_deliverable(order)
    existing = db.query(Delivery).filter(Delivery.order_id == order.id).first()
    delivery = ensure_delivery_document(db, order)
    write_audit_log(
        db,
        entity_type="delivery",
        entity_id=delivery.id,
        action=(AuditAction.CREATE if existing is None else AuditAction.UPDATE),
        after={"order_id": order.id, "delivery_no": delivery.delivery_no},
    )
    db.commit()
    db.refresh(delivery)
    return DeliveryResponse.model_validate(delivery)


@router.post(
    "/uuid/{order_uuid}/from-order",
    response_model=DeliveryResponse,
    responses={
        404: {"model": ApiErrorResponse, "description": "Not Found"},
        409: {"model": ApiErrorResponse, "description": "Conflict"},
        422: {"model": ApiErrorResponse, "description": "Validation Error"},
    },
)
def build_delivery_from_order_uuid(order_uuid: str, db: Session = Depends(get_db)) -> DeliveryResponse:
    order = _get_order_or_404(db, order_uuid)
    _assert_order_deliverable(order)
    existing = db.query(Delivery).filter(Delivery.order_id == order.id).first()
    delivery = ensure_delivery_document(db, order)
    write_audit_log(
        db,
        entity_type="delivery",
        entity_id=delivery.id,
        action=(AuditAction.CREATE if existing is None else AuditAction.UPDATE),
        after={"order_id": order.id, "delivery_no": delivery.delivery_no},
    )
    db.commit()
    db.refresh(delivery)
    return DeliveryResponse.model_validate(delivery)


@router.post(
    "/{delivery_id}/refresh",
    response_model=DeliveryResponse,
    responses={
        404: {"model": ApiErrorResponse, "description": "Not Found"},
        409: {"model": ApiErrorResponse, "description": "Conflict"},
    },
)
def refresh_delivery(delivery_id: str, db: Session = Depends(get_db)) -> DeliveryResponse:
    delivery = _get_delivery_or_404(db, delivery_id)
    order = _get_order_or_404(db, delivery.order_id)
    _assert_order_deliverable(order)
    refreshed = ensure_delivery_document(db, order)
    write_audit_log(
        db,
        entity_type="delivery",
        entity_id=refreshed.id,
        action=AuditAction.UPDATE,
        after={"order_id": order.id, "delivery_no": refreshed.delivery_no},
    )
    db.commit()
    db.refresh(refreshed)
    return DeliveryResponse.model_validate(refreshed)


@router.get(
    "/{delivery_id}/pdf",
    responses={
        200: {"content": {"application/pdf": {}}},
        404: {"model": ApiErrorResponse, "description": "Not Found"},
    },
)
def get_delivery_pdf(delivery_id: str, db: Session = Depends(get_db)) -> Response:
    delivery = _get_delivery_or_404(db, delivery_id)
    customer = db.query(Customer).filter(Customer.id == delivery.customer_id).first()
    if customer is None:
        raise HTTPException(status_code=404, detail={"code": "CUSTOMER_NOT_FOUND", "message": "customer not found"})

    rows = (
        db.query(DeliveryItem, Product, OrderItem)
        .join(Product, Product.id == DeliveryItem.product_id)
        .join(OrderItem, OrderItem.id == DeliveryItem.order_item_id)
        .filter(DeliveryItem.delivery_id == delivery.id)
        .order_by(DeliveryItem.created_at.asc())
        .all()
    )
    if not rows:
        raise HTTPException(status_code=404, detail={"code": "DELIVERY_ITEMS_NOT_FOUND", "message": "delivery items not found"})

    font = _pick_font()
    buf = BytesIO()
    pdf = canvas.Canvas(buf, pagesize=A4, pageCompression=1)
    width, height = A4
    pdf.setFont(font, 14)
    pdf.drawString(36, height - 40, f"Delivery No: {delivery.delivery_no}")
    pdf.setFont(font, 11)
    pdf.drawString(36, height - 60, f"Customer: {customer.name}")
    pdf.drawString(36, height - 76, f"Shipped Date: {delivery.shipped_date.isoformat()}")
    pdf.drawString(36, height - 92, f"Tracking No: {delivery.tracking_no or '-'}")

    y = height - 130
    pdf.setFont(font, 10)
    pdf.drawString(36, y, "Line")
    pdf.drawString(120, y, "Product")
    pdf.drawString(360, y, "Qty")
    pdf.drawString(430, y, "UOM")
    y -= 16

    for item, product, _order_item in rows:
        if y < 48:
            pdf.showPage()
            pdf.setFont(font, 10)
            y = height - 40
        pdf.drawString(36, y, item.delivery_line_no)
        pdf.drawString(120, y, product.name)
        pdf.drawRightString(410, y, f"{float(item.delivered_qty):.3f}".rstrip("0").rstrip("."))
        pdf.drawString(430, y, item.delivered_uom)
        y -= 16

    pdf.save()
    return Response(content=buf.getvalue(), media_type="application/pdf")


@router.get(
    "/uuid/{delivery_uuid}/pdf",
    responses={
        200: {"content": {"application/pdf": {}}},
        404: {"model": ApiErrorResponse, "description": "Not Found"},
    },
)
def get_delivery_pdf_by_uuid(delivery_uuid: str, db: Session = Depends(get_db)) -> Response:
    return get_delivery_pdf(delivery_uuid, db)
