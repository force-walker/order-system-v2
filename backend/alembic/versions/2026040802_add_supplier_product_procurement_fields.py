"""add supplier_product procurement fields

Revision ID: 2026040802
Revises: 2026040801
Create Date: 2026-04-08 11:24:00
"""

from alembic import op
import sqlalchemy as sa


revision = "2026040802"
down_revision = "2026040801"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("supplier_products", sa.Column("default_unit_cost", sa.Numeric(12, 2), nullable=True))
    op.add_column("supplier_products", sa.Column("lead_time_days", sa.Integer(), nullable=True))

    op.create_check_constraint(
        "ck_supplier_products_default_unit_cost_non_negative",
        "supplier_products",
        "default_unit_cost IS NULL OR default_unit_cost >= 0",
    )
    op.create_check_constraint(
        "ck_supplier_products_lead_time_days_non_negative",
        "supplier_products",
        "lead_time_days IS NULL OR lead_time_days >= 0",
    )


def downgrade() -> None:
    op.drop_constraint("ck_supplier_products_lead_time_days_non_negative", "supplier_products", type_="check")
    op.drop_constraint("ck_supplier_products_default_unit_cost_non_negative", "supplier_products", type_="check")
    op.drop_column("supplier_products", "lead_time_days")
    op.drop_column("supplier_products", "default_unit_cost")
