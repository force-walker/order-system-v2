"""Add permanent document and line numbering foundations.

Revision ID: 2026092002
Revises: 2026092001
"""

from alembic import op
import sqlalchemy as sa


revision = "2026092002"
down_revision = "2026092001"
branch_labels = None
depends_on = None


SEQUENCES = (
    "order_document_seq",
    "delivery_document_seq",
    "invoice_document_seq",
    "official_invoice_document_seq",
    "orders_legacy_id_seq",
    "order_items_legacy_id_seq",
    "invoices_legacy_id_seq",
    "invoice_items_legacy_id_seq",
)


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for name in SEQUENCES:
            op.execute(sa.text(f"CREATE SEQUENCE IF NOT EXISTS {name} START WITH 1 INCREMENT BY 1 NO CYCLE"))

    op.add_column("orders", sa.Column("document_seq", sa.BigInteger(), nullable=True))
    op.add_column("orders", sa.Column("next_line_no", sa.Integer(), nullable=True))
    op.add_column("order_items", sa.Column("line_no", sa.Integer(), nullable=True))
    op.add_column("order_items", sa.Column("line_ref", sa.String(length=32), nullable=True))

    op.add_column("deliveries", sa.Column("document_seq", sa.BigInteger(), nullable=True))
    op.add_column("deliveries", sa.Column("next_line_no", sa.Integer(), nullable=True))
    op.add_column("delivery_items", sa.Column("line_no", sa.Integer(), nullable=True))
    op.add_column("delivery_items", sa.Column("line_ref", sa.String(length=32), nullable=True))

    op.add_column("invoices", sa.Column("document_seq", sa.BigInteger(), nullable=True))
    op.add_column("invoices", sa.Column("official_document_seq", sa.BigInteger(), nullable=True))
    op.add_column("invoices", sa.Column("next_line_no", sa.Integer(), nullable=True))
    op.add_column("invoices", sa.Column("delivery_id", sa.String(length=36), nullable=True))
    op.add_column("invoice_items", sa.Column("line_no", sa.Integer(), nullable=True))
    op.add_column("invoice_items", sa.Column("line_ref", sa.String(length=32), nullable=True))

    op.create_index("ix_invoices_delivery_id", "invoices", ["delivery_id"], unique=False)
    if bind.dialect.name == "postgresql":
        op.create_foreign_key("fk_invoices_delivery_id_deliveries", "invoices", "deliveries", ["delivery_id"], ["id"])


def downgrade():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.drop_constraint("fk_invoices_delivery_id_deliveries", "invoices", type_="foreignkey")
    op.drop_index("ix_invoices_delivery_id", table_name="invoices")
    for table, columns in (
        ("invoice_items", ("line_ref", "line_no")),
        ("invoices", ("delivery_id", "next_line_no", "official_document_seq", "document_seq")),
        ("delivery_items", ("line_ref", "line_no")),
        ("deliveries", ("next_line_no", "document_seq")),
        ("order_items", ("line_ref", "line_no")),
        ("orders", ("next_line_no", "document_seq")),
    ):
        for column in columns:
            op.drop_column(table, column)
    if bind.dialect.name == "postgresql":
        for name in reversed(SEQUENCES):
            op.execute(sa.text(f"DROP SEQUENCE IF EXISTS {name}"))
