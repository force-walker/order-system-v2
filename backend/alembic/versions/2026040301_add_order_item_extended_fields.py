"""add extended order_item fields for frontend PR19

Revision ID: 2026040301
Revises: 2026032810
Create Date: 2026-04-03 11:45:00
"""

from alembic import op
import sqlalchemy as sa


revision = "2026040301"
down_revision = "2026032810"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("order_items", sa.Column("target_price", sa.Numeric(12, 2), nullable=True))
    op.add_column("order_items", sa.Column("price_ceiling", sa.Numeric(12, 2), nullable=True))
    op.add_column(
        "order_items",
        sa.Column(
            "stockout_policy",
            sa.Enum("backorder", "substitute", "cancel", "split", name="stockoutpolicy", create_type=False),
            nullable=True,
        ),
    )
    op.add_column("order_items", sa.Column("comment", sa.Text(), nullable=True))

    op.create_check_constraint(
        "ck_order_items_target_price_non_negative",
        "order_items",
        "target_price IS NULL OR target_price >= 0",
    )
    op.create_check_constraint(
        "ck_order_items_price_ceiling_non_negative",
        "order_items",
        "price_ceiling IS NULL OR price_ceiling >= 0",
    )


def downgrade() -> None:
    op.drop_constraint("ck_order_items_price_ceiling_non_negative", "order_items", type_="check")
    op.drop_constraint("ck_order_items_target_price_non_negative", "order_items", type_="check")

    op.drop_column("order_items", "comment")
    op.drop_column("order_items", "stockout_policy")
    op.drop_column("order_items", "price_ceiling")
    op.drop_column("order_items", "target_price")
