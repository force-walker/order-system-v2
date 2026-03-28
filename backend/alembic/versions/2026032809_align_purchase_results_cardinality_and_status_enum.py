"""align purchase_results cardinality and result_status enum

Revision ID: 2026032809
Revises: 2026032808
Create Date: 2026-03-28 09:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "2026032809"
down_revision = "2026032808"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("uq_purchase_results_allocation_id", "purchase_results", type_="unique")

    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'purchaseresultstatus') THEN
                CREATE TYPE purchaseresultstatus AS ENUM ('not_filled', 'filled', 'partially_filled', 'substituted');
            END IF;
        END
        $$;
        """
    )

    op.execute(
        """
        ALTER TABLE purchase_results
        ALTER COLUMN result_status TYPE purchaseresultstatus
        USING result_status::purchaseresultstatus
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE purchase_results
        ALTER COLUMN result_status TYPE VARCHAR(32)
        USING result_status::text
        """
    )
    op.execute("DROP TYPE IF EXISTS purchaseresultstatus")

    op.create_unique_constraint("uq_purchase_results_allocation_id", "purchase_results", ["allocation_id"])
