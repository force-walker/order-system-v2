"""add freight_weight to products

Revision ID: 2026061602
Revises: 2026061601
Create Date: 2026-06-16
"""

from alembic import op
import sqlalchemy as sa


revision = "2026061602"
down_revision = "2026061601"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("products", sa.Column("freight_weight", sa.Numeric(12, 3), nullable=True))


def downgrade() -> None:
    op.drop_column("products", "freight_weight")
