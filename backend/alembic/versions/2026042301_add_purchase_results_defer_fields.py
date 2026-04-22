"""add defer management fields to purchase_results

Revision ID: 2026042301
Revises: 2026042101
Create Date: 2026-04-23 00:35:00
"""

from alembic import op
import sqlalchemy as sa


revision = "2026042301"
down_revision = "2026042101"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("purchase_results", sa.Column("is_deferred", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("purchase_results", sa.Column("defer_until", sa.DateTime(), nullable=True))
    op.add_column("purchase_results", sa.Column("defer_reason", sa.String(length=255), nullable=True))
    op.add_column("purchase_results", sa.Column("deferred_by", sa.String(length=64), nullable=True))
    op.add_column("purchase_results", sa.Column("deferred_at", sa.DateTime(), nullable=True))

    op.create_index("ix_purchase_results_is_deferred", "purchase_results", ["is_deferred"], unique=False)
    op.create_index("ix_purchase_results_defer_until", "purchase_results", ["defer_until"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_purchase_results_defer_until", table_name="purchase_results")
    op.drop_index("ix_purchase_results_is_deferred", table_name="purchase_results")
    op.drop_column("purchase_results", "deferred_at")
    op.drop_column("purchase_results", "deferred_by")
    op.drop_column("purchase_results", "defer_reason")
    op.drop_column("purchase_results", "defer_until")
    op.drop_column("purchase_results", "is_deferred")
