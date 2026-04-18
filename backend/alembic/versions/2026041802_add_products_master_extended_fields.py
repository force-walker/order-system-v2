"""add extended product master fields for migration import

Revision ID: 2026041802
Revises: 2026041801
Create Date: 2026-04-18 20:55:00
"""

from alembic import op
import sqlalchemy as sa


revision = "2026041802"
down_revision = "2026041801"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("products", sa.Column("category_code", sa.String(length=16), nullable=True))
    op.add_column("products", sa.Column("product_type_code", sa.String(length=16), nullable=True))
    op.add_column("products", sa.Column("name_kana", sa.String(length=255), nullable=True))
    op.add_column("products", sa.Column("name_kana_key", sa.String(length=64), nullable=True))
    op.add_column("products", sa.Column("pack_size", sa.Integer(), nullable=True))
    op.add_column("products", sa.Column("tax_category_code", sa.String(length=16), nullable=True))
    op.add_column("products", sa.Column("inventory_category_code", sa.String(length=16), nullable=True))
    op.add_column("products", sa.Column("owner_code", sa.String(length=32), nullable=True))
    op.add_column("products", sa.Column("origin_code", sa.String(length=32), nullable=True))
    op.add_column("products", sa.Column("jan_code", sa.String(length=32), nullable=True))

    for c in [
        "sales_price",
        "sales_price_1",
        "sales_price_2",
        "sales_price_3",
        "sales_price_4",
        "sales_price_5",
        "sales_price_6",
        "purchase_price",
        "inventory_price",
        "list_price",
        "customs_reference_price",
    ]:
        op.add_column("products", sa.Column(c, sa.Numeric(12, 2), nullable=True))

    op.add_column("products", sa.Column("tax_rate_code", sa.String(length=16), nullable=True))
    op.add_column("products", sa.Column("handling_category_code", sa.String(length=16), nullable=True))
    op.add_column("products", sa.Column("name_en", sa.String(length=255), nullable=True))
    op.add_column("products", sa.Column("name_zh_hk", sa.String(length=255), nullable=True))
    op.add_column("products", sa.Column("customs_origin_text", sa.String(length=255), nullable=True))
    op.add_column("products", sa.Column("remarks", sa.Text(), nullable=True))
    op.add_column("products", sa.Column("chayafuda_flag", sa.Boolean(), nullable=True))
    op.add_column("products", sa.Column("application_category_code", sa.String(length=16), nullable=True))


def downgrade() -> None:
    for c in [
        "application_category_code",
        "chayafuda_flag",
        "remarks",
        "customs_origin_text",
        "name_zh_hk",
        "name_en",
        "handling_category_code",
        "tax_rate_code",
        "customs_reference_price",
        "list_price",
        "inventory_price",
        "purchase_price",
        "sales_price_6",
        "sales_price_5",
        "sales_price_4",
        "sales_price_3",
        "sales_price_2",
        "sales_price_1",
        "sales_price",
        "jan_code",
        "origin_code",
        "owner_code",
        "inventory_category_code",
        "tax_category_code",
        "pack_size",
        "name_kana_key",
        "name_kana",
        "product_type_code",
        "category_code",
    ]:
        op.drop_column("products", c)
