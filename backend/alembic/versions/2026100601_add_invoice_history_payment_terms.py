"""Add payment terms and invoice payment tracking.

Revision ID: 2026100601
Revises: 2026092008
"""
from alembic import op
import sqlalchemy as sa

revision = "2026100601"
down_revision = "2026092008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("customers", "suppliers"):
        op.add_column(table, sa.Column("payment_terms_type", sa.String(32), nullable=True))
        op.add_column(table, sa.Column("payment_terms_days", sa.Integer(), nullable=True))
        op.create_check_constraint(f"ck_{table}_payment_terms_days_non_negative", table,
            "payment_terms_days IS NULL OR payment_terms_days >= 0")
        op.create_check_constraint(f"ck_{table}_payment_terms_type", table,
            "payment_terms_type IS NULL OR payment_terms_type IN ('days_after_issue','end_of_issue_month','end_of_next_month','end_of_second_month','half_month_15_eom')")
    op.add_column("invoices", sa.Column("payment_status", sa.String(32), nullable=False, server_default="unpaid"))
    op.create_index("ix_invoices_due_date", "invoices", ["due_date"])
    op.create_index("ix_invoices_invoice_date", "invoices", ["invoice_date"])
    op.create_index("ix_invoices_payment_status", "invoices", ["payment_status"])
    op.create_check_constraint("ck_invoices_payment_status", "invoices", "payment_status IN ('unpaid','partially_paid','paid')")


def downgrade() -> None:
    op.drop_constraint("ck_invoices_payment_status", "invoices", type_="check")
    op.drop_index("ix_invoices_payment_status", table_name="invoices")
    op.drop_index("ix_invoices_invoice_date", table_name="invoices")
    op.drop_index("ix_invoices_due_date", table_name="invoices")
    op.drop_column("invoices", "payment_status")
    for table in ("suppliers", "customers"):
        op.drop_constraint(f"ck_{table}_payment_terms_days_non_negative", table, type_="check")
        op.drop_constraint(f"ck_{table}_payment_terms_type", table, type_="check")
        op.drop_column(table, "payment_terms_days")
        op.drop_column(table, "payment_terms_type")
