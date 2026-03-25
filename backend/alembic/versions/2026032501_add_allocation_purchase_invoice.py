"""add allocation, purchase_results, and invoices tables

Revision ID: 2026032501
Revises: 82789dd533d2
Create Date: 2026-03-25 18:25:00
"""

from alembic import op
import sqlalchemy as sa


revision = "2026032501"
down_revision = "82789dd533d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    stockout_policy = sa.Enum("backorder", "substitute", "cancel", "split", name="stockoutpolicy")
    invoice_status = sa.Enum("draft", "finalized", "sent", "cancelled", name="invoicestatus")
    stockout_policy.create(op.get_bind(), checkfirst=True)
    invoice_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "supplier_allocations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_item_id", sa.Integer(), nullable=False),
        sa.Column("final_supplier_id", sa.Integer(), nullable=True),
        sa.Column("final_qty", sa.Numeric(12, 3), nullable=True),
        sa.Column("final_uom", sa.String(length=32), nullable=True),
        sa.Column("is_manual_override", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("override_reason_code", sa.String(length=64), nullable=True),
        sa.Column("stockout_policy", stockout_policy, nullable=True),
        sa.Column("split_group_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["order_item_id"], ["order_items.id"]),
    )
    op.create_index("ix_supplier_allocations_order_item_id", "supplier_allocations", ["order_item_id"])
    op.create_index("ix_supplier_allocations_split_group_id", "supplier_allocations", ["split_group_id"])

    op.create_table(
        "purchase_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("allocation_id", sa.Integer(), nullable=False),
        sa.Column("purchased_qty", sa.Numeric(12, 3), nullable=False),
        sa.Column("purchased_uom", sa.String(length=32), nullable=False),
        sa.Column("result_status", sa.String(length=32), nullable=False),
        sa.Column("invoiceable_flag", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("recorded_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["allocation_id"], ["supplier_allocations.id"]),
    )
    op.create_index("ix_purchase_results_allocation_id", "purchase_results", ["allocation_id"])
    op.create_index("ix_purchase_results_result_status", "purchase_results", ["result_status"])

    op.create_table(
        "invoices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("invoice_no", sa.String(length=64), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("invoice_date", sa.Date(), nullable=False),
        sa.Column("delivery_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("subtotal", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("tax_total", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("grand_total", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("status", invoice_status, nullable=False, server_default="draft"),
        sa.Column("is_locked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.UniqueConstraint("invoice_no", name="uq_invoices_invoice_no"),
    )
    op.create_index("ix_invoices_invoice_no", "invoices", ["invoice_no"])
    op.create_index("ix_invoices_customer_id", "invoices", ["customer_id"])
    op.create_index("ix_invoices_status", "invoices", ["status"])


def downgrade() -> None:
    op.drop_index("ix_invoices_status", table_name="invoices")
    op.drop_index("ix_invoices_customer_id", table_name="invoices")
    op.drop_index("ix_invoices_invoice_no", table_name="invoices")
    op.drop_table("invoices")

    op.drop_index("ix_purchase_results_result_status", table_name="purchase_results")
    op.drop_index("ix_purchase_results_allocation_id", table_name="purchase_results")
    op.drop_table("purchase_results")

    op.drop_index("ix_supplier_allocations_split_group_id", table_name="supplier_allocations")
    op.drop_index("ix_supplier_allocations_order_item_id", table_name="supplier_allocations")
    op.drop_table("supplier_allocations")

    sa.Enum(name="invoicestatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="stockoutpolicy").drop(op.get_bind(), checkfirst=True)
