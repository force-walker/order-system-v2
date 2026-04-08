"""add supplier_products mapping table

Revision ID: 2026040801
Revises: 2026040601
Create Date: 2026-04-08 09:35:00
"""

from alembic import op
import sqlalchemy as sa


revision = "2026040801"
down_revision = "2026040601"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "supplier_products",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("supplier_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("is_preferred", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_supplier_products_supplier_id"), "supplier_products", ["supplier_id"], unique=False)
    op.create_index(op.f("ix_supplier_products_product_id"), "supplier_products", ["product_id"], unique=False)
    op.create_index("ix_supplier_products_supplier_id_product_id", "supplier_products", ["supplier_id", "product_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_supplier_products_supplier_id_product_id", table_name="supplier_products")
    op.drop_index(op.f("ix_supplier_products_product_id"), table_name="supplier_products")
    op.drop_index(op.f("ix_supplier_products_supplier_id"), table_name="supplier_products")
    op.drop_table("supplier_products")
