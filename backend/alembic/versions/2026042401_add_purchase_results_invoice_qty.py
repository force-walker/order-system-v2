"""add invoice_qty to purchase_results

Revision ID: 2026042401
Revises: 2026042301
Create Date: 2026-04-24 00:12:00
"""

from alembic import op
import sqlalchemy as sa


revision = "2026042401"
down_revision = "2026042301"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("purchase_results", sa.Column("invoice_qty", sa.Numeric(12, 3), nullable=True))


def downgrade() -> None:
    op.drop_column("purchase_results", "invoice_qty")
