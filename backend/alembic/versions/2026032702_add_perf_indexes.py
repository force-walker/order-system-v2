"""add minimal performance indexes for audit and batch hot paths

Revision ID: 2026032702
Revises: 2026032701
Create Date: 2026-03-27 15:30:00
"""

from alembic import op


revision = "2026032702"
down_revision = "2026032701"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_batch_jobs_type_business_date_status",
        "batch_jobs",
        ["job_type", "business_date", "status"],
        unique=False,
    )
    op.create_index(
        "ix_audit_logs_entity_type_entity_id_changed_at",
        "audit_logs",
        ["entity_type", "entity_id", "changed_at"],
        unique=False,
    )
    op.create_index(
        "ix_audit_logs_changed_by_changed_at",
        "audit_logs",
        ["changed_by", "changed_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_audit_logs_changed_by_changed_at", table_name="audit_logs")
    op.drop_index("ix_audit_logs_entity_type_entity_id_changed_at", table_name="audit_logs")
    op.drop_index("ix_batch_jobs_type_business_date_status", table_name="batch_jobs")
