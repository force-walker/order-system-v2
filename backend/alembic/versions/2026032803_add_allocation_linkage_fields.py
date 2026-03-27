"""add supplier_allocation suggested/target/split-linkage fields

Revision ID: 2026032803
Revises: 2026032802
Create Date: 2026-03-28 02:35:00
"""

from alembic import op
import sqlalchemy as sa


revision = "2026032803"
down_revision = "2026032802"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("supplier_allocations", sa.Column("suggested_supplier_id", sa.Integer(), nullable=True))
    op.add_column("supplier_allocations", sa.Column("suggested_qty", sa.Numeric(12, 3), nullable=True))
    op.add_column("supplier_allocations", sa.Column("target_price", sa.Numeric(12, 2), nullable=True))
    op.add_column("supplier_allocations", sa.Column("parent_allocation_id", sa.Integer(), nullable=True))
    op.add_column(
        "supplier_allocations",
        sa.Column("is_split_child", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )

    op.create_foreign_key(
        "fk_supplier_allocations_parent_allocation_id",
        "supplier_allocations",
        "supplier_allocations",
        ["parent_allocation_id"],
        ["id"],
    )

    op.create_check_constraint(
        "ck_supplier_allocations_suggested_qty_positive",
        "supplier_allocations",
        "suggested_qty IS NULL OR suggested_qty > 0",
    )

    op.create_index(
        "ix_supplier_allocations_suggested_supplier_id",
        "supplier_allocations",
        ["suggested_supplier_id"],
        unique=False,
    )
    op.create_index(
        "ix_supplier_allocations_parent_allocation_id",
        "supplier_allocations",
        ["parent_allocation_id"],
        unique=False,
    )
    op.create_index(
        "ix_supplier_allocations_is_split_child",
        "supplier_allocations",
        ["is_split_child"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_supplier_allocations_is_split_child", table_name="supplier_allocations")
    op.drop_index("ix_supplier_allocations_parent_allocation_id", table_name="supplier_allocations")
    op.drop_index("ix_supplier_allocations_suggested_supplier_id", table_name="supplier_allocations")

    op.drop_constraint("ck_supplier_allocations_suggested_qty_positive", "supplier_allocations", type_="check")
    op.drop_constraint("fk_supplier_allocations_parent_allocation_id", "supplier_allocations", type_="foreignkey")

    op.drop_column("supplier_allocations", "is_split_child")
    op.drop_column("supplier_allocations", "parent_allocation_id")
    op.drop_column("supplier_allocations", "target_price")
    op.drop_column("supplier_allocations", "suggested_qty")
    op.drop_column("supplier_allocations", "suggested_supplier_id")
