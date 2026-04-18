"""add products legacy fields for migration period

Revision ID: 2026041801
Revises: 2026041601
Create Date: 2026-04-18 17:25:00
"""

from alembic import op
import sqlalchemy as sa


revision = "2026041801"
down_revision = "2026041601"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("products", sa.Column("legacy_code", sa.String(length=128), nullable=True))
    op.add_column("products", sa.Column("legacy_unit_code", sa.String(length=64), nullable=True))
    op.create_index(op.f("ix_products_legacy_code"), "products", ["legacy_code"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_products_legacy_code"), table_name="products")
    op.drop_column("products", "legacy_unit_code")
    op.drop_column("products", "legacy_code")
