"""add shipped_date to orders

Revision ID: 2026041401
Revises: 2026040803
Create Date: 2026-04-14 22:30:00
"""

from alembic import op
import sqlalchemy as sa


revision = "2026041401"
down_revision = "2026040803"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("shipped_date", sa.Date(), nullable=True))
    op.create_index(op.f("ix_orders_shipped_date"), "orders", ["shipped_date"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_orders_shipped_date"), table_name="orders")
    op.drop_column("orders", "shipped_date")
