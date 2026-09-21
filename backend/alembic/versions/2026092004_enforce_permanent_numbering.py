"""Enforce permanent numbering constraints and sequence-backed legacy IDs."""

from alembic import op
import sqlalchemy as sa


revision = "2026092004"
down_revision = "2026092003"
branch_labels = None
depends_on = None


DOCUMENTS = ("orders", "deliveries", "invoices")
DETAILS = (
    ("order_items", "order_id", "uq_order_items_order_id_line_no", "ck_order_items_line_no_positive"),
    ("delivery_items", "delivery_id", "uq_delivery_items_delivery_id_line_no", "ck_delivery_items_line_no_positive"),
    ("invoice_items", "invoice_id", "uq_invoice_items_invoice_id_line_no", "ck_invoice_items_line_no_positive"),
)


def _assert_backfill_complete(bind) -> None:
    checks = [
        ("orders", "document_seq IS NULL OR next_line_no IS NULL"),
        ("deliveries", "document_seq IS NULL OR next_line_no IS NULL"),
        ("invoices", "document_seq IS NULL OR next_line_no IS NULL"),
        ("order_items", "line_no IS NULL OR line_ref IS NULL"),
        ("delivery_items", "line_no IS NULL OR line_ref IS NULL"),
        ("invoice_items", "line_no IS NULL OR line_ref IS NULL"),
    ]
    for table, predicate in checks:
        count = int(bind.execute(sa.text(f"SELECT COUNT(*) FROM {table} WHERE {predicate}")).scalar_one())
        if count:
            raise RuntimeError(f"numbering backfill incomplete: {table} has {count} invalid rows")


def upgrade():
    bind = op.get_bind()
    _assert_backfill_complete(bind)

    for table in DOCUMENTS:
        with op.batch_alter_table(table) as batch:
            batch.alter_column("document_seq", existing_type=sa.BigInteger(), nullable=False)
            batch.alter_column("next_line_no", existing_type=sa.Integer(), nullable=False, server_default=sa.text("10"))
            batch.create_unique_constraint(f"uq_{table}_document_seq", ["document_seq"])
            batch.create_check_constraint(f"ck_{table}_next_line_no_positive", "next_line_no > 0")

    with op.batch_alter_table("invoices") as batch:
        batch.create_unique_constraint("uq_invoices_official_document_seq", ["official_document_seq"])

    for table, parent_fk, unique_name, check_name in DETAILS:
        with op.batch_alter_table(table) as batch:
            batch.alter_column("line_no", existing_type=sa.Integer(), nullable=False)
            batch.alter_column("line_ref", existing_type=sa.String(length=32), nullable=False)
            batch.create_unique_constraint(unique_name, [parent_fk, "line_no"])
            batch.create_unique_constraint(f"uq_{table}_line_ref", ["line_ref"])
            batch.create_check_constraint(check_name, "line_no > 0")

    if bind.dialect.name == "postgresql":
        for table, sequence in (
            ("orders", "orders_legacy_id_seq"),
            ("order_items", "order_items_legacy_id_seq"),
            ("invoices", "invoices_legacy_id_seq"),
            ("invoice_items", "invoice_items_legacy_id_seq"),
        ):
            op.execute(sa.text(f"ALTER TABLE {table} ALTER COLUMN legacy_id SET DEFAULT nextval('{sequence}')"))


def downgrade():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for table in ("orders", "order_items", "invoices", "invoice_items"):
            op.execute(sa.text(f"ALTER TABLE {table} ALTER COLUMN legacy_id DROP DEFAULT"))

    for table, _parent_fk, unique_name, check_name in reversed(DETAILS):
        with op.batch_alter_table(table) as batch:
            batch.drop_constraint(check_name, type_="check")
            batch.drop_constraint(f"uq_{table}_line_ref", type_="unique")
            batch.drop_constraint(unique_name, type_="unique")
            batch.alter_column("line_ref", existing_type=sa.String(length=32), nullable=True)
            batch.alter_column("line_no", existing_type=sa.Integer(), nullable=True)

    with op.batch_alter_table("invoices") as batch:
        batch.drop_constraint("uq_invoices_official_document_seq", type_="unique")
    for table in reversed(DOCUMENTS):
        with op.batch_alter_table(table) as batch:
            batch.drop_constraint(f"ck_{table}_next_line_no_positive", type_="check")
            batch.drop_constraint(f"uq_{table}_document_seq", type_="unique")
            batch.alter_column("next_line_no", existing_type=sa.Integer(), nullable=True, server_default=None)
            batch.alter_column("document_seq", existing_type=sa.BigInteger(), nullable=True)
