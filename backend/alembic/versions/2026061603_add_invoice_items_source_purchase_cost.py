"""add invoice item source purchase unit cost jpy

Revision ID: 2026061603
Revises: 2026061602
Create Date: 2026-06-16
"""

from alembic import op
import sqlalchemy as sa


revision = "2026061603"
down_revision = "2026061602"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("invoice_items", sa.Column("source_purchase_unit_cost_jpy", sa.Numeric(12, 2), nullable=True))


def downgrade() -> None:
    op.drop_column("invoice_items", "source_purchase_unit_cost_jpy")
