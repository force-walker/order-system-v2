"""add uuid shadow columns

Revision ID: 2026061902
Revises: 2026061901
Create Date: 2026-06-19 15:55:00
"""

from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision = "2026061902"
down_revision = "2026061901"
branch_labels = None
depends_on = None


def _backfill_uuid_column(table_name: str) -> None:
    bind = op.get_bind()
    rows = bind.execute(sa.text(f"SELECT id FROM {table_name} WHERE uuid IS NULL")).fetchall()
    for row in rows:
        bind.execute(
            sa.text(f"UPDATE {table_name} SET uuid = :uuid WHERE id = :id"),
            {"uuid": str(uuid4()), "id": row.id},
        )


def upgrade() -> None:
    op.add_column("orders", sa.Column("uuid", sa.String(length=36), nullable=True))
    _backfill_uuid_column("orders")
    op.alter_column("orders", "uuid", nullable=False)
    op.create_index(op.f("ix_orders_uuid"), "orders", ["uuid"], unique=True)

    op.add_column("order_items", sa.Column("uuid", sa.String(length=36), nullable=True))
    _backfill_uuid_column("order_items")
    op.alter_column("order_items", "uuid", nullable=False)
    op.create_index(op.f("ix_order_items_uuid"), "order_items", ["uuid"], unique=True)

    op.add_column("invoices", sa.Column("uuid", sa.String(length=36), nullable=True))
    _backfill_uuid_column("invoices")
    op.alter_column("invoices", "uuid", nullable=False)
    op.create_index(op.f("ix_invoices_uuid"), "invoices", ["uuid"], unique=True)

    op.add_column("invoice_items", sa.Column("uuid", sa.String(length=36), nullable=True))
    _backfill_uuid_column("invoice_items")
    op.alter_column("invoice_items", "uuid", nullable=False)
    op.create_index(op.f("ix_invoice_items_uuid"), "invoice_items", ["uuid"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_invoice_items_uuid"), table_name="invoice_items")
    op.drop_column("invoice_items", "uuid")

    op.drop_index(op.f("ix_invoices_uuid"), table_name="invoices")
    op.drop_column("invoices", "uuid")

    op.drop_index(op.f("ix_order_items_uuid"), table_name="order_items")
    op.drop_column("order_items", "uuid")

    op.drop_index(op.f("ix_orders_uuid"), table_name="orders")
    op.drop_column("orders", "uuid")
