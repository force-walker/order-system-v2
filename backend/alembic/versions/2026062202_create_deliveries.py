"""create deliveries tables

Revision ID: 2026062202
Revises: 2026062201
Create Date: 2026-06-22 12:40:00
"""

from alembic import op
import sqlalchemy as sa


revision = "2026062202"
down_revision = "2026062201"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "deliveries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("delivery_no", sa.String(length=32), nullable=False),
        sa.Column("tracking_no", sa.String(length=32), nullable=True),
        sa.Column("order_id", sa.String(length=36), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("delivery_date", sa.Date(), nullable=False),
        sa.Column("shipped_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_deliveries_delivery_no"), "deliveries", ["delivery_no"], unique=True)
    op.create_index(op.f("ix_deliveries_tracking_no"), "deliveries", ["tracking_no"], unique=False)
    op.create_index(op.f("ix_deliveries_order_id"), "deliveries", ["order_id"], unique=True)
    op.create_index(op.f("ix_deliveries_customer_id"), "deliveries", ["customer_id"], unique=False)
    op.create_index(op.f("ix_deliveries_delivery_date"), "deliveries", ["delivery_date"], unique=False)
    op.create_index(op.f("ix_deliveries_shipped_date"), "deliveries", ["shipped_date"], unique=False)

    op.create_table(
        "delivery_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("delivery_id", sa.String(length=36), nullable=False),
        sa.Column("order_item_id", sa.String(length=36), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("delivery_line_no", sa.String(length=32), nullable=False),
        sa.Column("delivered_qty", sa.Numeric(12, 3), nullable=False),
        sa.Column("delivered_uom", sa.String(length=32), nullable=False),
        sa.Column("shipped_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["delivery_id"], ["deliveries.id"]),
        sa.ForeignKeyConstraint(["order_item_id"], ["order_items.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_delivery_items_delivery_id"), "delivery_items", ["delivery_id"], unique=False)
    op.create_index(op.f("ix_delivery_items_order_item_id"), "delivery_items", ["order_item_id"], unique=True)
    op.create_index(op.f("ix_delivery_items_product_id"), "delivery_items", ["product_id"], unique=False)
    op.create_index(op.f("ix_delivery_items_delivery_line_no"), "delivery_items", ["delivery_line_no"], unique=True)
    op.create_index(op.f("ix_delivery_items_shipped_date"), "delivery_items", ["shipped_date"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_delivery_items_shipped_date"), table_name="delivery_items")
    op.drop_index(op.f("ix_delivery_items_delivery_line_no"), table_name="delivery_items")
    op.drop_index(op.f("ix_delivery_items_product_id"), table_name="delivery_items")
    op.drop_index(op.f("ix_delivery_items_order_item_id"), table_name="delivery_items")
    op.drop_index(op.f("ix_delivery_items_delivery_id"), table_name="delivery_items")
    op.drop_table("delivery_items")

    op.drop_index(op.f("ix_deliveries_shipped_date"), table_name="deliveries")
    op.drop_index(op.f("ix_deliveries_delivery_date"), table_name="deliveries")
    op.drop_index(op.f("ix_deliveries_customer_id"), table_name="deliveries")
    op.drop_index(op.f("ix_deliveries_order_id"), table_name="deliveries")
    op.drop_index(op.f("ix_deliveries_tracking_no"), table_name="deliveries")
    op.drop_index(op.f("ix_deliveries_delivery_no"), table_name="deliveries")
    op.drop_table("deliveries")
