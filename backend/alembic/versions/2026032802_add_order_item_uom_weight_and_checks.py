"""add order_items uom/weight columns and pricing-basis check

Revision ID: 2026032802
Revises: 2026032801
Create Date: 2026-03-28 00:40:00
"""

from alembic import op
import sqlalchemy as sa


revision = "2026032802"
down_revision = "2026032801"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "order_items",
        sa.Column(
            "order_uom_type",
            sa.Enum("uom_count", "uom_kg", name="pricingbasis", create_type=False),
            nullable=False,
            server_default="uom_count",
        ),
    )
    op.add_column("order_items", sa.Column("estimated_weight_kg", sa.Numeric(12, 3), nullable=True))
    op.add_column("order_items", sa.Column("actual_weight_kg", sa.Numeric(12, 3), nullable=True))

    op.create_check_constraint(
        "ck_order_items_price_required_by_pricing_basis",
        "order_items",
        "(pricing_basis != 'uom_count' OR unit_price_uom_count IS NOT NULL)"
        " AND (pricing_basis != 'uom_kg' OR unit_price_uom_kg IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_order_items_price_required_by_pricing_basis", "order_items", type_="check")
    op.drop_column("order_items", "actual_weight_kg")
    op.drop_column("order_items", "estimated_weight_kg")
    op.drop_column("order_items", "order_uom_type")
