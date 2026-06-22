import re
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.entities import Invoice, InvoiceItem, Order, OrderItem

HK_TZ = ZoneInfo("Asia/Hong_Kong")

_TRACKING_RE = re.compile(r"^(?P<date>\d{8})-(?P<seq>\d{5})$")
_DELIVERY_RE = re.compile(r"^DLV-(?P<date>\d{8})-(?P<seq>\d{5})-(?P<branch>\d{2})$")
_ORDER_LINE_RE = re.compile(r"^ODL-(?P<seq>\d{5})-(?P<line>\d{4})$")
_INVOICE_DRAFT_RE = re.compile(r"^IVD-(?P<date>\d{8})-(?P<seq>\d{5})-(?P<branch>\d{2})$")
_INVOICE_LINE_RE = re.compile(r"^IVL-(?P<seq>\d{5})-(?P<branch>\d{2})-(?P<line>\d{4})$")
_OFFICIAL_INVOICE_RE = re.compile(r"^INV/(?P<year>\d{4})/(?P<seq>\d{5})$")


def _max_sequence(values: list[str | None], pattern: re.Pattern[str], group: str) -> int:
    current = 0
    for value in values:
        if not value:
            continue
        match = pattern.match(value)
        if not match:
            continue
        current = max(current, int(match.group(group)))
    return current


def _next_legacy_id(db: Session, table_name: str) -> int:
    row = db.execute(text(f"SELECT COALESCE(MAX(legacy_id), 0) + 1 FROM {table_name}")).first()
    return int(row[0])


def ensure_order_legacy_id(db: Session, order: Order) -> None:
    if order.legacy_id is None:
        order.legacy_id = _next_legacy_id(db, Order.__tablename__)


def ensure_order_item_legacy_id(db: Session, item: OrderItem) -> None:
    if item.legacy_id is None:
        item.legacy_id = _next_legacy_id(db, OrderItem.__tablename__)


def ensure_invoice_legacy_id(db: Session, invoice: Invoice) -> None:
    if invoice.legacy_id is None:
        invoice.legacy_id = _next_legacy_id(db, Invoice.__tablename__)


def ensure_invoice_item_legacy_id(db: Session, item: InvoiceItem) -> None:
    if item.legacy_id is None:
        item.legacy_id = _next_legacy_id(db, InvoiceItem.__tablename__)


def _tracking_parts(tracking_no: str | None, fallback_order_id: int | None) -> tuple[str, str]:
    if tracking_no:
        match = _TRACKING_RE.match(tracking_no)
        if match:
            return match.group("date"), match.group("seq")
    fallback = fallback_order_id or 0
    return datetime.now(HK_TZ).strftime("%Y%m%d"), str(fallback).zfill(5)[-5:]


def generate_tracking_no(db: Session, *, now_hk: datetime | None = None) -> str:
    now_hk = now_hk or datetime.now(HK_TZ)
    date_code = now_hk.strftime("%Y%m%d")
    prefix = f"{date_code}-"
    existing = [
        value
        for (value,) in db.query(Order.tracking_no).filter(Order.tracking_no.like(f"{prefix}%")).all()
        if value is not None
    ]
    next_seq = _max_sequence(existing, _TRACKING_RE, "seq") + 1
    return f"{date_code}-{next_seq:05d}"


def generate_order_no(tracking_no: str) -> str:
    return f"ORD-{tracking_no}"


def ensure_order_header_numbers(db: Session, order: Order, *, now_hk: datetime | None = None) -> None:
    if order.tracking_no and order.order_no and not order.order_no.startswith("pending-"):
        return
    ensure_order_legacy_id(db, order)
    tracking_no = order.tracking_no or generate_tracking_no(db, now_hk=now_hk)
    order.tracking_no = tracking_no
    if not order.order_no or order.order_no.startswith("pending-"):
        order.order_no = generate_order_no(tracking_no)


def generate_delivery_no(db: Session, order: Order) -> str:
    date_code, seq = _tracking_parts(order.tracking_no, order.legacy_id)
    prefix = f"DLV-{date_code}-{seq}-"
    existing = [
        value
        for (value,) in db.query(Order.delivery_no).filter(Order.delivery_no.like(f"{prefix}%")).all()
        if value is not None
    ]
    branch = _max_sequence(existing, _DELIVERY_RE, "branch") + 1
    return f"DLV-{date_code}-{seq}-{branch:02d}"


def ensure_order_delivery_number(db: Session, order: Order, *, now_hk: datetime | None = None) -> None:
    if order.delivery_no:
        return
    ensure_order_header_numbers(db, order, now_hk=now_hk)
    order.delivery_no = generate_delivery_no(db, order)


def generate_order_line_no(db: Session, order: Order) -> str:
    _date_code, seq = _tracking_parts(order.tracking_no, order.legacy_id)
    existing = [
        value
        for (value,) in db.query(OrderItem.order_line_no).filter(OrderItem.order_id == order.id).all()
        if value is not None
    ]
    next_line = _max_sequence(existing, _ORDER_LINE_RE, "line") + 1
    return f"ODL-{seq}-{next_line:04d}"


def ensure_order_item_number(db: Session, order: Order, item: OrderItem) -> None:
    if item.order_line_no:
        return
    ensure_order_item_legacy_id(db, item)
    item.order_line_no = generate_order_line_no(db, order)


def generate_invoice_draft_no(db: Session, order: Order) -> tuple[str, str]:
    tracking_no = order.tracking_no or generate_tracking_no(db)
    date_code, seq = _tracking_parts(tracking_no, order.legacy_id)
    prefix = f"IVD-{date_code}-{seq}-"
    existing = [
        value
        for (value,) in db.query(Invoice.invoice_draft_no).filter(Invoice.invoice_draft_no.like(f"{prefix}%")).all()
        if value is not None
    ]
    branch = _max_sequence(existing, _INVOICE_DRAFT_RE, "branch") + 1
    return tracking_no, f"IVD-{date_code}-{seq}-{branch:02d}"


def _invoice_branch_parts(invoice: Invoice) -> tuple[str, str]:
    match = _INVOICE_DRAFT_RE.match(invoice.invoice_draft_no or "")
    if match:
        return match.group("seq"), match.group("branch")
    _date_code, seq = _tracking_parts(invoice.tracking_no, invoice.legacy_id)
    return seq, "01"


def generate_invoice_line_no(db: Session, invoice: Invoice) -> str:
    seq, branch = _invoice_branch_parts(invoice)
    existing = [
        value
        for (value,) in db.query(InvoiceItem.invoice_line_no).filter(InvoiceItem.invoice_id == invoice.id).all()
        if value is not None
    ]
    next_line = _max_sequence(existing, _INVOICE_LINE_RE, "line") + 1
    return f"IVL-{seq}-{branch}-{next_line:04d}"


def ensure_invoice_item_number(db: Session, invoice: Invoice, item: InvoiceItem) -> None:
    if item.invoice_line_no:
        return
    ensure_invoice_item_legacy_id(db, item)
    item.invoice_line_no = generate_invoice_line_no(db, invoice)


def generate_official_invoice_no(db: Session, invoice: Invoice) -> str:
    year = invoice.invoice_date.year
    result = db.execute(
        text(
            """
            INSERT INTO invoice_number_sequences (year, next_seq, updated_at)
            VALUES (:year, 2, CURRENT_TIMESTAMP)
            ON CONFLICT(year)
            DO UPDATE SET
                next_seq = invoice_number_sequences.next_seq + 1,
                updated_at = CURRENT_TIMESTAMP
            RETURNING next_seq - 1 AS allocated_seq
            """
        ),
        {"year": year},
    ).first()
    allocated_seq = int(result[0])
    return f"INV/{year}/{allocated_seq:05d}"
