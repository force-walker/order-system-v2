"""relax supplier_allocation final_qty constraint to allow zero

Revision ID: 2026032808
Revises: 2026032807
Create Date: 2026-03-28 08:52:00
"""

from alembic import op


revision = "2026032808"
down_revision = "2026032807"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_supplier_allocations_final_qty_positive", "supplier_allocations", type_="check")
    op.create_check_constraint(
        "ck_supplier_allocations_final_qty_non_negative",
        "supplier_allocations",
        "final_qty IS NULL OR final_qty >= 0",
    )


def downgrade() -> None:
    op.drop_constraint("ck_supplier_allocations_final_qty_non_negative", "supplier_allocations", type_="check")
    op.create_check_constraint(
        "ck_supplier_allocations_final_qty_positive",
        "supplier_allocations",
        "final_qty IS NULL OR final_qty > 0",
    )
