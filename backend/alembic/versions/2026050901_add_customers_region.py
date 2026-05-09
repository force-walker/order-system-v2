"""add customers.region

Revision ID: 2026050901
Revises: 2026042401
Create Date: 2026-05-09
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "2026050901"
down_revision = "2026042401"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("customers", sa.Column("region", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("customers", "region")
