"""Permanent document and line numbering.

UUIDs remain the internal identifiers. ``document_seq`` and ``line_no`` are
immutable business numbers, while ``line_ref`` is the human-readable globally
unique line reference. The legacy ``*_line_no`` columns are dual-written for
new rows only as field compatibility; their historical format is deprecated.
"""

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.entities import Delivery, DeliveryItem, Invoice, InvoiceItem, Order, OrderItem

LEGACY_SEQUENCES = {
    "orders": "orders_legacy_id_seq",
    "order_items": "order_items_legacy_id_seq",
    "invoices": "invoices_legacy_id_seq",
    "invoice_items": "invoice_items_legacy_id_seq",
}


def _next_sequence_value(db: Session, sequence_name: str, table_name: str, column_name: str) -> int:
    """Allocate with a PostgreSQL sequence; use a deterministic SQLite fallback."""
    if db.get_bind().dialect.name == "postgresql":
        return int(db.execute(text(f"SELECT nextval('{sequence_name}')")).scalar_one())
    value = db.execute(text(f"SELECT COALESCE(MAX({column_name}), 0) + 1 FROM {table_name}")).scalar_one()
    return int(value)


def _next_legacy_id(db: Session, table_name: str) -> int:
    return _next_sequence_value(db, LEGACY_SEQUENCES[table_name], table_name, "legacy_id")


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


def ensure_order_header_numbers(db: Session, order: Order, **_: object) -> None:
    ensure_order_legacy_id(db, order)
    if order.document_seq is None:
        order.document_seq = _next_sequence_value(db, "order_document_seq", "orders", "document_seq")
    if not order.order_no or order.order_no.startswith("pending-"):
        order.order_no = f"ORD-{order.document_seq:08d}"
    if not order.tracking_no:
        order.tracking_no = f"TRK-{order.document_seq:08d}"
    if order.next_line_no is None:
        order.next_line_no = 10


def ensure_delivery_header_numbers(db: Session, delivery: Delivery) -> None:
    if delivery.document_seq is None:
        delivery.document_seq = _next_sequence_value(db, "delivery_document_seq", "deliveries", "document_seq")
    if not delivery.delivery_no or delivery.delivery_no == "pending":
        delivery.delivery_no = f"DEL-{delivery.document_seq:08d}"
    if delivery.next_line_no is None:
        delivery.next_line_no = 10


def ensure_invoice_header_numbers(db: Session, invoice: Invoice) -> None:
    ensure_invoice_legacy_id(db, invoice)
    if invoice.document_seq is None:
        invoice.document_seq = _next_sequence_value(db, "invoice_document_seq", "invoices", "document_seq")
    if not invoice.invoice_draft_no:
        invoice.invoice_draft_no = f"IVD-{invoice.document_seq:08d}"
    if not invoice.invoice_no or invoice.invoice_no.startswith("pending-"):
        invoice.invoice_no = invoice.invoice_draft_no
    if invoice.next_line_no is None:
        invoice.next_line_no = 10


def ensure_order_delivery_number(db: Session, order: Order, **_: object) -> None:
    """Compatibility helper; Delivery owns the authoritative delivery number."""
    ensure_order_header_numbers(db, order)


def _allocate_parent_line_no(db: Session, table_name: str, parent_id: str) -> tuple[int, int]:
    row = db.execute(
        text(
            f"UPDATE {table_name} "
            "SET next_line_no = COALESCE(next_line_no, 10) + 10 "
            "WHERE id = :parent_id "
            "RETURNING next_line_no - 10 AS line_no, document_seq"
        ),
        {"parent_id": parent_id},
    ).first()
    if row is None or row[1] is None:
        raise ValueError(f"{table_name} header numbering is not initialized")
    return int(row[0]), int(row[1])


def ensure_order_item_number(db: Session, order: Order, item: OrderItem) -> None:
    if order.document_seq is None:
        ensure_order_header_numbers(db, order)
        db.flush()
    ensure_order_item_legacy_id(db, item)
    if item.line_no is None:
        item.line_no, document_seq = _allocate_parent_line_no(db, "orders", order.id)
    else:
        document_seq = int(order.document_seq or 0)
    if item.line_ref is None:
        item.line_ref = f"ODL-{document_seq:08d}-{item.line_no:04d}"
    # Deprecated field compatibility, not compatibility with the old value format.
    if not item.order_line_no:
        item.order_line_no = item.line_ref


def ensure_delivery_item_number(db: Session, delivery: Delivery, item: DeliveryItem) -> None:
    if delivery.document_seq is None:
        ensure_delivery_header_numbers(db, delivery)
        db.flush()
    if item.line_no is None:
        item.line_no, document_seq = _allocate_parent_line_no(db, "deliveries", delivery.id)
    else:
        document_seq = int(delivery.document_seq or 0)
    if item.line_ref is None:
        item.line_ref = f"DLI-{document_seq:08d}-{item.line_no:04d}"
    # Deprecated field compatibility, not compatibility with the old value format.
    if not item.delivery_line_no or item.delivery_line_no == "pending":
        item.delivery_line_no = item.line_ref


def ensure_invoice_item_number(db: Session, invoice: Invoice, item: InvoiceItem) -> None:
    if invoice.document_seq is None:
        ensure_invoice_header_numbers(db, invoice)
        db.flush()
    ensure_invoice_item_legacy_id(db, item)
    if item.line_no is None:
        item.line_no, document_seq = _allocate_parent_line_no(db, "invoices", invoice.id)
    else:
        document_seq = int(invoice.document_seq or 0)
    if item.line_ref is None:
        item.line_ref = f"IVL-{document_seq:08d}-{item.line_no:04d}"
    # Deprecated field compatibility, not compatibility with the old value format.
    if not item.invoice_line_no:
        item.invoice_line_no = item.line_ref


def generate_official_invoice_no(db: Session, invoice: Invoice) -> str:
    if invoice.official_document_seq is None:
        invoice.official_document_seq = _next_sequence_value(
            db,
            "official_invoice_document_seq",
            "invoices",
            "official_document_seq",
        )
    return f"INV-{invoice.official_document_seq:08d}"
