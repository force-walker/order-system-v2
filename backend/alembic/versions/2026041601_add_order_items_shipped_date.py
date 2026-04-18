"""add shipped_date to order_items

Revision ID: 2026041601
Revises: 2026041401
Create Date: 2026-04-16 22:20:00
"""

from alembic import op
import sqlalchemy as sa


revision = "2026041601"
down_revision = "2026041401"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("order_items", sa.Column("shipped_date", sa.Date(), nullable=True))
    op.create_index(op.f("ix_order_items_shipped_date"), "order_items", ["shipped_date"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_order_items_shipped_date"), table_name="order_items")
    op.drop_column("order_items", "shipped_date")
