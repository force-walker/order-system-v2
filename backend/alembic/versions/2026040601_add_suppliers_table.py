"""add suppliers master table

Revision ID: 2026040601
Revises: 2026040301
Create Date: 2026-04-06 16:03:00
"""

from alembic import op
import sqlalchemy as sa


revision = "2026040601"
down_revision = "2026040301"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "suppliers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("supplier_code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("supplier_code"),
    )
    op.create_index(op.f("ix_suppliers_supplier_code"), "suppliers", ["supplier_code"], unique=False)
    op.create_index(op.f("ix_suppliers_name"), "suppliers", ["name"], unique=False)
    op.create_index(op.f("ix_suppliers_active"), "suppliers", ["active"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_suppliers_active"), table_name="suppliers")
    op.drop_index(op.f("ix_suppliers_name"), table_name="suppliers")
    op.drop_index(op.f("ix_suppliers_supplier_code"), table_name="suppliers")
    op.drop_table("suppliers")
