"""add invoice number sequences

Revision ID: 2026061903
Revises: 2026061902
Create Date: 2026-06-19 20:18:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "2026061903"
down_revision = "2026061902"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "invoice_number_sequences",
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("next_seq", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("year >= 2000", name="ck_invoice_number_sequences_year_min"),
        sa.CheckConstraint("next_seq >= 1", name="ck_invoice_number_sequences_next_seq_positive"),
        sa.PrimaryKeyConstraint("year"),
    )


def downgrade() -> None:
    op.drop_table("invoice_number_sequences")
