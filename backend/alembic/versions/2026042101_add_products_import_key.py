"""add import_key to products for import upsert

Revision ID: 2026042101
Revises: 2026041802
Create Date: 2026-04-21 01:35:00
"""

from alembic import op
import sqlalchemy as sa


revision = "2026042101"
down_revision = "2026041802"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("products", sa.Column("import_key", sa.String(length=128), nullable=True))
    op.create_index("ix_products_import_key", "products", ["import_key"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_products_import_key", table_name="products")
    op.drop_column("products", "import_key")
