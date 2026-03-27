"""create invoice_items table

Revision ID: 2026032805
Revises: 2026032804
Create Date: 2026-03-28 03:14:00
"""

from alembic import op
import sqlalchemy as sa


revision = "2026032805"
down_revision = "2026032804"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "invoice_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("invoice_id", sa.Integer(), nullable=False),
        sa.Column("order_item_id", sa.Integer(), nullable=False),
        sa.Column("billable_qty", sa.Numeric(12, 3), nullable=False),
        sa.Column("billable_uom", sa.String(32), nullable=False),
        sa.Column(
            "invoice_line_status",
            sa.Enum("uninvoiced", "partially_invoiced", "invoiced", "cancelled", name="invoicelinestatus"),
            nullable=False,
            server_default="uninvoiced",
        ),
        sa.Column("sales_unit_price", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("unit_cost_basis", sa.Numeric(12, 2), nullable=True),
        sa.Column("line_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("tax_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"]),
        sa.ForeignKeyConstraint(["order_item_id"], ["order_items.id"]),
        sa.CheckConstraint("sales_unit_price >= 0", name="ck_invoice_items_sales_unit_price_non_negative"),
    )

    op.create_index("ix_invoice_items_invoice_id", "invoice_items", ["invoice_id"], unique=False)
    op.create_index("ix_invoice_items_order_item_id", "invoice_items", ["order_item_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_invoice_items_order_item_id", table_name="invoice_items")
    op.drop_index("ix_invoice_items_invoice_id", table_name="invoice_items")
    op.drop_table("invoice_items")
    op.execute("DROP TYPE IF EXISTS invoicelinestatus")
