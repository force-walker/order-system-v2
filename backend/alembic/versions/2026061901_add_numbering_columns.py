"""add numbering columns

Revision ID: 2026061901
Revises: 2026061603
Create Date: 2026-06-19 15:40:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "2026061901"
down_revision = "2026061603"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("tracking_no", sa.String(length=32), nullable=True))
    op.create_index(op.f("ix_orders_tracking_no"), "orders", ["tracking_no"], unique=True)

    op.add_column("order_items", sa.Column("order_line_no", sa.String(length=32), nullable=True))
    op.create_index(op.f("ix_order_items_order_line_no"), "order_items", ["order_line_no"], unique=True)

    op.add_column("invoices", sa.Column("tracking_no", sa.String(length=32), nullable=True))
    op.create_index(op.f("ix_invoices_tracking_no"), "invoices", ["tracking_no"], unique=False)
    op.add_column("invoices", sa.Column("invoice_draft_no", sa.String(length=32), nullable=True))
    op.create_index(op.f("ix_invoices_invoice_draft_no"), "invoices", ["invoice_draft_no"], unique=True)
    op.add_column("invoices", sa.Column("official_invoice_no", sa.String(length=32), nullable=True))
    op.create_index(op.f("ix_invoices_official_invoice_no"), "invoices", ["official_invoice_no"], unique=True)

    op.add_column("invoice_items", sa.Column("invoice_line_no", sa.String(length=32), nullable=True))
    op.create_index(op.f("ix_invoice_items_invoice_line_no"), "invoice_items", ["invoice_line_no"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_invoice_items_invoice_line_no"), table_name="invoice_items")
    op.drop_column("invoice_items", "invoice_line_no")

    op.drop_index(op.f("ix_invoices_official_invoice_no"), table_name="invoices")
    op.drop_column("invoices", "official_invoice_no")
    op.drop_index(op.f("ix_invoices_invoice_draft_no"), table_name="invoices")
    op.drop_column("invoices", "invoice_draft_no")
    op.drop_index(op.f("ix_invoices_tracking_no"), table_name="invoices")
    op.drop_column("invoices", "tracking_no")

    op.drop_index(op.f("ix_order_items_order_line_no"), table_name="order_items")
    op.drop_column("order_items", "order_line_no")

    op.drop_index(op.f("ix_orders_tracking_no"), table_name="orders")
    op.drop_column("orders", "tracking_no")
