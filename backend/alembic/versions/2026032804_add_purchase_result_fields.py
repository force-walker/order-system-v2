"""add purchase_results required operational fields

Revision ID: 2026032804
Revises: 2026032803
Create Date: 2026-03-28 02:56:00
"""

from alembic import op
import sqlalchemy as sa


revision = "2026032804"
down_revision = "2026032803"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'stockoutpolicy') THEN
                CREATE TYPE stockoutpolicy AS ENUM ('backorder', 'substitute', 'cancel', 'split');
            END IF;
        END
        $$;
        """
    )

    op.add_column("purchase_results", sa.Column("supplier_id", sa.Integer(), nullable=True))
    op.add_column("purchase_results", sa.Column("actual_weight_kg", sa.Numeric(12, 3), nullable=True))
    op.add_column("purchase_results", sa.Column("unit_cost", sa.Numeric(12, 2), nullable=True))
    op.add_column("purchase_results", sa.Column("final_unit_cost", sa.Numeric(12, 2), nullable=True))
    op.add_column("purchase_results", sa.Column("shortage_qty", sa.Numeric(12, 3), nullable=True))
    op.add_column(
        "purchase_results",
        sa.Column(
            "shortage_policy",
            sa.Enum("backorder", "substitute", "cancel", "split", name="stockoutpolicy", create_type=False),
            nullable=True,
        ),
    )
    op.add_column("purchase_results", sa.Column("recorded_by", sa.String(64), nullable=True))

    op.create_check_constraint(
        "ck_purchase_results_actual_weight_positive",
        "purchase_results",
        "actual_weight_kg IS NULL OR actual_weight_kg > 0",
    )
    op.create_check_constraint(
        "ck_purchase_results_unit_cost_non_negative",
        "purchase_results",
        "unit_cost IS NULL OR unit_cost >= 0",
    )
    op.create_check_constraint(
        "ck_purchase_results_final_unit_cost_non_negative",
        "purchase_results",
        "final_unit_cost IS NULL OR final_unit_cost >= 0",
    )
    op.create_check_constraint(
        "ck_purchase_results_shortage_qty_non_negative",
        "purchase_results",
        "shortage_qty IS NULL OR shortage_qty >= 0",
    )

    op.create_index("ix_purchase_results_supplier_id", "purchase_results", ["supplier_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_purchase_results_supplier_id", table_name="purchase_results")

    op.drop_constraint("ck_purchase_results_shortage_qty_non_negative", "purchase_results", type_="check")
    op.drop_constraint("ck_purchase_results_final_unit_cost_non_negative", "purchase_results", type_="check")
    op.drop_constraint("ck_purchase_results_unit_cost_non_negative", "purchase_results", type_="check")
    op.drop_constraint("ck_purchase_results_actual_weight_positive", "purchase_results", type_="check")

    op.drop_column("purchase_results", "recorded_by")
    op.drop_column("purchase_results", "shortage_policy")
    op.drop_column("purchase_results", "shortage_qty")
    op.drop_column("purchase_results", "final_unit_cost")
    op.drop_column("purchase_results", "unit_cost")
    op.drop_column("purchase_results", "actual_weight_kg")
    op.drop_column("purchase_results", "supplier_id")
