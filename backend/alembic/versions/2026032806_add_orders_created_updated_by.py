"""add created_by and updated_by to orders

Revision ID: 2026032806
Revises: 2026032805
Create Date: 2026-03-28 03:24:00
"""

from alembic import op
import sqlalchemy as sa


revision = "2026032806"
down_revision = "2026032805"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column("created_by", sa.String(length=64), nullable=False, server_default="system_api"),
    )
    op.add_column(
        "orders",
        sa.Column("updated_by", sa.String(length=64), nullable=False, server_default="system_api"),
    )

    op.create_index("ix_orders_created_by", "orders", ["created_by"], unique=False)
    op.create_index("ix_orders_updated_by", "orders", ["updated_by"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_orders_updated_by", table_name="orders")
    op.drop_index("ix_orders_created_by", table_name="orders")
    op.drop_column("orders", "updated_by")
    op.drop_column("orders", "created_by")
