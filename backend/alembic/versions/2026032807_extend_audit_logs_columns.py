"""extend audit_logs with before/after and correlation ids

Revision ID: 2026032807
Revises: 2026032806
Create Date: 2026-03-28 08:18:00
"""

from alembic import op
import sqlalchemy as sa


revision = "2026032807"
down_revision = "2026032806"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("audit_logs", sa.Column("before_json", sa.Text(), nullable=True))
    op.add_column("audit_logs", sa.Column("after_json", sa.Text(), nullable=True))
    op.add_column("audit_logs", sa.Column("trace_id", sa.String(length=64), nullable=True))
    op.add_column("audit_logs", sa.Column("request_id", sa.String(length=64), nullable=True))
    op.add_column("audit_logs", sa.Column("job_id", sa.String(length=64), nullable=True))

    op.create_index("ix_audit_logs_trace_id", "audit_logs", ["trace_id"], unique=False)
    op.create_index("ix_audit_logs_request_id", "audit_logs", ["request_id"], unique=False)
    op.create_index("ix_audit_logs_job_id", "audit_logs", ["job_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_audit_logs_job_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_request_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_trace_id", table_name="audit_logs")

    op.drop_column("audit_logs", "job_id")
    op.drop_column("audit_logs", "request_id")
    op.drop_column("audit_logs", "trace_id")
    op.drop_column("audit_logs", "after_json")
    op.drop_column("audit_logs", "before_json")
