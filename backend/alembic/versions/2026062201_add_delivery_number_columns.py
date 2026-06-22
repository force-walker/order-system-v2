"""add delivery number columns

Revision ID: 2026062201
Revises: 2026061904
Create Date: 2026-06-22 10:20:00
"""

from alembic import op
import sqlalchemy as sa


revision = "2026062201"
down_revision = "2026061904"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("delivery_no", sa.String(length=32), nullable=True))
    op.create_index(op.f("ix_orders_delivery_no"), "orders", ["delivery_no"], unique=True)

    op.add_column("invoices", sa.Column("delivery_no", sa.String(length=32), nullable=True))
    op.create_index(op.f("ix_invoices_delivery_no"), "invoices", ["delivery_no"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_invoices_delivery_no"), table_name="invoices")
    op.drop_column("invoices", "delivery_no")

    op.drop_index(op.f("ix_orders_delivery_no"), table_name="orders")
    op.drop_column("orders", "delivery_no")
