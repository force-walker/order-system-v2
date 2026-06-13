"""add import_key to customers and suppliers

Revision ID: 2026061301
Revises: 2026050901
Create Date: 2026-06-13
"""

from alembic import op
import sqlalchemy as sa


revision = "2026061301"
down_revision = "2026050901"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("customers", sa.Column("import_key", sa.String(length=128), nullable=True))
    op.create_index("ix_customers_import_key", "customers", ["import_key"], unique=True)

    op.add_column("suppliers", sa.Column("import_key", sa.String(length=128), nullable=True))
    op.create_index("ix_suppliers_import_key", "suppliers", ["import_key"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_suppliers_import_key", table_name="suppliers")
    op.drop_column("suppliers", "import_key")

    op.drop_index("ix_customers_import_key", table_name="customers")
    op.drop_column("customers", "import_key")
