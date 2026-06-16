"""add system settings singleton

Revision ID: 2026061601
Revises: 2026061301
Create Date: 2026-06-16
"""

from alembic import op
import sqlalchemy as sa


revision = "2026061601"
down_revision = "2026061301"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "system_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("exchange_rate", sa.Numeric(12, 4), nullable=False),
        sa.Column("jp_gross_margin_pct", sa.Numeric(7, 3), nullable=False),
        sa.Column("hk_gross_margin_pct", sa.Numeric(7, 3), nullable=False),
        sa.Column("freight_unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_system_settings_singleton_id"),
        sa.CheckConstraint("exchange_rate > 0", name="ck_system_settings_exchange_rate_positive"),
        sa.CheckConstraint("jp_gross_margin_pct >= 0", name="ck_system_settings_jp_gross_margin_pct_non_negative"),
        sa.CheckConstraint("hk_gross_margin_pct >= 0", name="ck_system_settings_hk_gross_margin_pct_non_negative"),
        sa.CheckConstraint("freight_unit_price >= 0", name="ck_system_settings_freight_unit_price_non_negative"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(
        sa.text(
            """
            INSERT INTO system_settings (
                id,
                exchange_rate,
                jp_gross_margin_pct,
                hk_gross_margin_pct,
                freight_unit_price,
                updated_at
            ) VALUES (
                1,
                1.0000,
                25.000,
                25.000,
                0.00,
                CURRENT_TIMESTAMP
            )
            """
        )
    )


def downgrade() -> None:
    op.drop_table("system_settings")
