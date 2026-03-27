"""rename customers.code to customers.customer_code

Revision ID: 2026032801
Revises: 2026032702
Create Date: 2026-03-28 00:28:00
"""

from alembic import op


revision = "2026032801"
down_revision = "2026032702"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("customers", "code", new_column_name="customer_code")


def downgrade() -> None:
    op.alter_column("customers", "customer_code", new_column_name="code")
