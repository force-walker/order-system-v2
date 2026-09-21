"""Backfill permanent numbering without changing UUIDs or legacy number strings.

Existing ``*_line_no`` values are intentionally untouched. New ``line_ref``
values use the new format and are not copies of the legacy values.
"""

from alembic import op
import sqlalchemy as sa


revision = "2026092003"
down_revision = "2026092002"
branch_labels = None
depends_on = None


def _rows(bind, table: str):
    return bind.execute(sa.text(f"SELECT id FROM {table} ORDER BY created_at, id")).fetchall()


def _backfill_document(bind, table: str, items: str, parent_fk: str, prefix: str) -> int:
    headers = _rows(bind, table)
    for seq, (header_id,) in enumerate(headers, 1):
        bind.execute(sa.text(f"UPDATE {table} SET document_seq=:seq WHERE id=:id"), {"seq": seq, "id": header_id})
        item_rows = bind.execute(
            sa.text(f"SELECT id FROM {items} WHERE {parent_fk}=:id ORDER BY created_at, id"),
            {"id": header_id},
        ).fetchall()
        for position, (item_id,) in enumerate(item_rows, 1):
            line_no = position * 10
            line_ref = f"{prefix}-{seq:08d}-{line_no:04d}"
            bind.execute(
                sa.text(f"UPDATE {items} SET line_no=:line_no, line_ref=:line_ref WHERE id=:id"),
                {"line_no": line_no, "line_ref": line_ref, "id": item_id},
            )
        bind.execute(
            sa.text(f"UPDATE {table} SET next_line_no=:next_line_no WHERE id=:id"),
            {"next_line_no": (len(item_rows) + 1) * 10, "id": header_id},
        )
    return len(headers)


def _set_pg_sequence(bind, name: str, value: int) -> None:
    if value > 0:
        bind.execute(sa.text("SELECT setval(:name, :value, true)"), {"name": name, "value": value})
    else:
        bind.execute(sa.text("SELECT setval(:name, 1, false)"), {"name": name})


def upgrade():
    bind = op.get_bind()
    order_count = _backfill_document(bind, "orders", "order_items", "order_id", "ODL")
    delivery_count = _backfill_document(bind, "deliveries", "delivery_items", "delivery_id", "DLI")
    invoice_count = _backfill_document(bind, "invoices", "invoice_items", "invoice_id", "IVL")

    finalized = bind.execute(
        sa.text("SELECT id FROM invoices WHERE official_invoice_no IS NOT NULL ORDER BY created_at, id")
    ).fetchall()
    for official_seq, (invoice_id,) in enumerate(finalized, 1):
        bind.execute(
            sa.text("UPDATE invoices SET official_document_seq=:seq WHERE id=:id"),
            {"seq": official_seq, "id": invoice_id},
        )

    bind.execute(
        sa.text(
            "UPDATE invoices SET delivery_id=(SELECT d.id FROM deliveries d "
            "WHERE d.delivery_no=invoices.delivery_no LIMIT 1) "
            "WHERE delivery_id IS NULL AND delivery_no IS NOT NULL"
        )
    )

    if bind.dialect.name == "postgresql":
        _set_pg_sequence(bind, "order_document_seq", order_count)
        _set_pg_sequence(bind, "delivery_document_seq", delivery_count)
        _set_pg_sequence(bind, "invoice_document_seq", invoice_count)
        _set_pg_sequence(bind, "official_invoice_document_seq", len(finalized))
        for table, sequence in (
            ("orders", "orders_legacy_id_seq"),
            ("order_items", "order_items_legacy_id_seq"),
            ("invoices", "invoices_legacy_id_seq"),
            ("invoice_items", "invoice_items_legacy_id_seq"),
        ):
            current = int(bind.execute(sa.text(f"SELECT COALESCE(MAX(legacy_id), 0) FROM {table}")).scalar_one())
            _set_pg_sequence(bind, sequence, current)


def downgrade():
    bind = op.get_bind()
    for table in ("orders", "deliveries", "invoices"):
        bind.execute(sa.text(f"UPDATE {table} SET document_seq=NULL, next_line_no=NULL"))
    bind.execute(sa.text("UPDATE invoices SET official_document_seq=NULL, delivery_id=NULL"))
    for table in ("order_items", "delivery_items", "invoice_items"):
        bind.execute(sa.text(f"UPDATE {table} SET line_no=NULL, line_ref=NULL"))
