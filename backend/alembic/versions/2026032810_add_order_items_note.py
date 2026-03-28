"""add note column to order_items

Revision ID: 2026032810
Revises: 2026032809
Create Date: 2026-03-28 10:35:00
"""

from alembic import op
import sqlalchemy as sa


revision = "2026032810"
down_revision = "2026032809"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("order_items", sa.Column("note", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("order_items", "note")
