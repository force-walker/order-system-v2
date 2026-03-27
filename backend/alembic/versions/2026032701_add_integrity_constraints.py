"""add integrity constraints for API-consistent validation/conflict handling

Revision ID: 2026032701
Revises: 2026032502
Create Date: 2026-03-27 09:35:00
"""

from alembic import op


revision = "2026032701"
down_revision = "2026032502"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # order_items
    op.create_check_constraint(
        "ck_order_items_ordered_qty_positive",
        "order_items",
        "ordered_qty > 0",
    )

    # supplier_allocations
    op.create_check_constraint(
        "ck_supplier_allocations_final_qty_positive",
        "supplier_allocations",
        "final_qty IS NULL OR final_qty > 0",
    )

    # purchase_results
    op.create_check_constraint(
        "ck_purchase_results_purchased_qty_positive",
        "purchase_results",
        "purchased_qty > 0",
    )
    op.create_unique_constraint(
        "uq_purchase_results_allocation_id",
        "purchase_results",
        ["allocation_id"],
    )

    # invoices
    op.create_check_constraint(
        "ck_invoices_due_date_gte_invoice_date",
        "invoices",
        "due_date IS NULL OR due_date >= invoice_date",
    )
    op.create_check_constraint(
        "ck_invoices_subtotal_non_negative",
        "invoices",
        "subtotal >= 0",
    )
    op.create_check_constraint(
        "ck_invoices_tax_total_non_negative",
        "invoices",
        "tax_total >= 0",
    )
    op.create_check_constraint(
        "ck_invoices_grand_total_non_negative",
        "invoices",
        "grand_total >= 0",
    )

    # batch_jobs
    op.create_check_constraint(
        "ck_batch_jobs_retry_count_non_negative",
        "batch_jobs",
        "retry_count >= 0",
    )
    op.create_check_constraint(
        "ck_batch_jobs_max_retries_min_one",
        "batch_jobs",
        "max_retries >= 1",
    )
    op.create_check_constraint(
        "ck_batch_jobs_retry_count_lte_max_retries",
        "batch_jobs",
        "retry_count <= max_retries",
    )
    op.create_check_constraint(
        "ck_batch_jobs_requested_count_non_negative",
        "batch_jobs",
        "requested_count >= 0",
    )
    op.create_check_constraint(
        "ck_batch_jobs_processed_count_non_negative",
        "batch_jobs",
        "processed_count >= 0",
    )
    op.create_check_constraint(
        "ck_batch_jobs_succeeded_count_non_negative",
        "batch_jobs",
        "succeeded_count >= 0",
    )
    op.create_check_constraint(
        "ck_batch_jobs_failed_count_non_negative",
        "batch_jobs",
        "failed_count >= 0",
    )
    op.create_check_constraint(
        "ck_batch_jobs_skipped_count_non_negative",
        "batch_jobs",
        "skipped_count >= 0",
    )


def downgrade() -> None:
    op.drop_constraint("ck_batch_jobs_skipped_count_non_negative", "batch_jobs", type_="check")
    op.drop_constraint("ck_batch_jobs_failed_count_non_negative", "batch_jobs", type_="check")
    op.drop_constraint("ck_batch_jobs_succeeded_count_non_negative", "batch_jobs", type_="check")
    op.drop_constraint("ck_batch_jobs_processed_count_non_negative", "batch_jobs", type_="check")
    op.drop_constraint("ck_batch_jobs_requested_count_non_negative", "batch_jobs", type_="check")
    op.drop_constraint("ck_batch_jobs_retry_count_lte_max_retries", "batch_jobs", type_="check")
    op.drop_constraint("ck_batch_jobs_max_retries_min_one", "batch_jobs", type_="check")
    op.drop_constraint("ck_batch_jobs_retry_count_non_negative", "batch_jobs", type_="check")

    op.drop_constraint("ck_invoices_grand_total_non_negative", "invoices", type_="check")
    op.drop_constraint("ck_invoices_tax_total_non_negative", "invoices", type_="check")
    op.drop_constraint("ck_invoices_subtotal_non_negative", "invoices", type_="check")
    op.drop_constraint("ck_invoices_due_date_gte_invoice_date", "invoices", type_="check")

    op.drop_constraint("uq_purchase_results_allocation_id", "purchase_results", type_="unique")
    op.drop_constraint("ck_purchase_results_purchased_qty_positive", "purchase_results", type_="check")

    op.drop_constraint("ck_supplier_allocations_final_qty_positive", "supplier_allocations", type_="check")

    op.drop_constraint("ck_order_items_ordered_qty_positive", "order_items", type_="check")
