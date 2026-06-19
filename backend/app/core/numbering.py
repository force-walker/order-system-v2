import re
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.models.entities import Invoice, InvoiceItem, Order, OrderItem

HK_TZ = ZoneInfo("Asia/Hong_Kong")

_TRACKING_RE = re.compile(r"^(?P<date>\d{8})-(?P<seq>\d{5})$")
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


def _tracking_parts(tracking_no: str | None, fallback_order_id: int) -> tuple[str, str]:
    if tracking_no:
        match = _TRACKING_RE.match(tracking_no)
        if match:
            return match.group("date"), match.group("seq")
    return datetime.now(HK_TZ).strftime("%Y%m%d"), str(fallback_order_id).zfill(5)[-5:]


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
    tracking_no = order.tracking_no or generate_tracking_no(db, now_hk=now_hk)
    order.tracking_no = tracking_no
    if not order.order_no or order.order_no.startswith("pending-"):
        order.order_no = generate_order_no(tracking_no)


def generate_order_line_no(db: Session, order: Order) -> str:
    _date_code, seq = _tracking_parts(order.tracking_no, order.id)
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
    item.order_line_no = generate_order_line_no(db, order)


def generate_invoice_draft_no(db: Session, order: Order) -> tuple[str, str]:
    tracking_no = order.tracking_no or generate_tracking_no(db)
    date_code, seq = _tracking_parts(tracking_no, order.id)
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
    _date_code, seq = _tracking_parts(invoice.tracking_no, invoice.id)
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
    item.invoice_line_no = generate_invoice_line_no(db, invoice)


def generate_official_invoice_no(db: Session, invoice: Invoice) -> str:
    year = invoice.invoice_date.year
    prefix = f"INV/{year}/"
    existing = [
        value
        for (value,) in db.query(Invoice.official_invoice_no).filter(Invoice.official_invoice_no.like(f"{prefix}%")).all()
        if value is not None
    ]
    next_seq = _max_sequence(existing, _OFFICIAL_INVOICE_RE, "seq") + 1
    return f"INV/{year}/{next_seq:05d}"
