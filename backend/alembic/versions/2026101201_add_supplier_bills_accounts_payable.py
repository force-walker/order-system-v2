"""Add Supplier Bill accounts payable domain.

Revision ID: 2026101201
Revises: 2026100602
"""
from alembic import op
import sqlalchemy as sa

revision = "2026101201"
down_revision = "2026100602"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table("supplier_bills",
        sa.Column("id",sa.String(36),primary_key=True), sa.Column("document_seq",sa.BigInteger,nullable=False),
        sa.Column("next_line_no",sa.Integer,nullable=False,server_default="10"), sa.Column("bill_no",sa.String(32),nullable=False),
        sa.Column("supplier_id",sa.Integer,sa.ForeignKey("suppliers.id"),nullable=False), sa.Column("supplier_invoice_no",sa.String(128),nullable=False),
        sa.Column("bill_date",sa.Date,nullable=False),sa.Column("due_date",sa.Date),sa.Column("payment_terms_type",sa.String(32)),sa.Column("payment_terms_days",sa.Integer),
        sa.Column("currency",sa.String(3),nullable=False,server_default="JPY"),sa.Column("status",sa.String(32),nullable=False,server_default="draft"),
        sa.Column("subtotal",sa.Numeric(14,2),nullable=False,server_default="0"),sa.Column("tax",sa.Numeric(14,2),nullable=False,server_default="0"),
        sa.Column("adjustment",sa.Numeric(14,2),nullable=False,server_default="0"),sa.Column("total_amount",sa.Numeric(14,2),nullable=False,server_default="0"),
        sa.Column("created_at",sa.DateTime,nullable=False),sa.Column("updated_at",sa.DateTime,nullable=False),
        sa.CheckConstraint("status IN ('draft','finalized','cancelled')",name="ck_supplier_bills_status"),
        sa.CheckConstraint("subtotal >= 0",name="ck_supplier_bills_subtotal_non_negative"),sa.CheckConstraint("total_amount >= 0",name="ck_supplier_bills_total_non_negative"),
        sa.UniqueConstraint("document_seq"),sa.UniqueConstraint("bill_no"))
    for col in ("document_seq","bill_no","supplier_id","supplier_invoice_no","bill_date","due_date","status"):
        op.create_index(f"ix_supplier_bills_{col}","supplier_bills",[col])
    op.create_table("supplier_bill_items",
        sa.Column("id",sa.String(36),primary_key=True),sa.Column("supplier_bill_id",sa.String(36),sa.ForeignKey("supplier_bills.id",ondelete="CASCADE"),nullable=False),
        sa.Column("line_no",sa.Integer,nullable=False),sa.Column("purchase_result_id",sa.Integer,sa.ForeignKey("purchase_results.id"),nullable=False),
        sa.Column("product_id",sa.Integer,sa.ForeignKey("products.id"),nullable=False),sa.Column("sku",sa.String(64),nullable=False),sa.Column("description",sa.String(255),nullable=False),
        sa.Column("quantity",sa.Numeric(12,3),nullable=False),sa.Column("uom",sa.String(32),nullable=False),sa.Column("unit_cost",sa.Numeric(14,2),nullable=True),sa.Column("line_amount",sa.Numeric(14,2),nullable=True),
        sa.Column("created_at",sa.DateTime,nullable=False),sa.Column("updated_at",sa.DateTime,nullable=False),
        sa.CheckConstraint("line_no > 0",name="ck_supplier_bill_items_line_no_positive"),sa.CheckConstraint("quantity > 0",name="ck_supplier_bill_items_quantity_positive"),
        sa.CheckConstraint("unit_cost IS NULL OR unit_cost >= 0",name="ck_supplier_bill_items_unit_cost_non_negative"),sa.CheckConstraint("line_amount IS NULL OR line_amount >= 0",name="ck_supplier_bill_items_line_amount_non_negative"),
        sa.UniqueConstraint("supplier_bill_id","line_no",name="uq_supplier_bill_items_bill_line_no"))
    op.create_index("ix_supplier_bill_items_supplier_bill_id","supplier_bill_items",["supplier_bill_id"])
    op.create_index("ix_supplier_bill_items_purchase_result_id","supplier_bill_items",["purchase_result_id"])
    op.create_index("ix_supplier_bill_items_product_id","supplier_bill_items",["product_id"])
    op.create_table("supplier_payments",
        sa.Column("id",sa.String(36),primary_key=True),sa.Column("supplier_bill_id",sa.String(36),sa.ForeignKey("supplier_bills.id"),nullable=False),
        sa.Column("payment_date",sa.Date,nullable=False),sa.Column("amount",sa.Numeric(14,2),nullable=False),sa.Column("reference",sa.String(128)),sa.Column("note",sa.Text),
        sa.Column("created_at",sa.DateTime,nullable=False),sa.Column("voided_at",sa.DateTime),sa.Column("void_reason",sa.String(255)),
        sa.CheckConstraint("amount > 0",name="ck_supplier_payments_amount_positive"))
    op.create_index("ix_supplier_payments_supplier_bill_id","supplier_payments",["supplier_bill_id"])
    op.create_index("ix_supplier_payments_payment_date","supplier_payments",["payment_date"])
    bind=op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE SEQUENCE IF NOT EXISTS supplier_bill_document_seq START WITH 1")
        op.execute("""CREATE FUNCTION reject_duplicate_active_purchase_result_claim() RETURNS trigger AS $$
        BEGIN
          PERFORM pg_advisory_xact_lock(NEW.purchase_result_id);
          IF EXISTS (SELECT 1 FROM supplier_bill_items i JOIN supplier_bills b ON b.id=i.supplier_bill_id
            WHERE i.purchase_result_id=NEW.purchase_result_id AND b.status <> 'cancelled' AND i.id <> NEW.id) THEN
            RAISE EXCEPTION 'purchase result already claimed' USING ERRCODE='23505';
          END IF; RETURN NEW;
        END; $$ LANGUAGE plpgsql""")
        op.execute("CREATE TRIGGER trg_supplier_bill_item_claim BEFORE INSERT OR UPDATE ON supplier_bill_items FOR EACH ROW EXECUTE FUNCTION reject_duplicate_active_purchase_result_claim()")
        op.execute("""CREATE FUNCTION reject_duplicate_supplier_invoice_no() RETURNS trigger AS $$
        BEGIN
          PERFORM pg_advisory_xact_lock(NEW.supplier_id, hashtext(NEW.supplier_invoice_no));
          IF NEW.status <> 'cancelled' AND EXISTS (SELECT 1 FROM supplier_bills b WHERE b.supplier_id=NEW.supplier_id
            AND b.supplier_invoice_no=NEW.supplier_invoice_no AND b.status <> 'cancelled' AND b.id <> NEW.id) THEN
            RAISE EXCEPTION 'supplier invoice number already exists' USING ERRCODE='23505';
          END IF; RETURN NEW;
        END; $$ LANGUAGE plpgsql""")
        op.execute("CREATE TRIGGER trg_supplier_invoice_no_unique BEFORE INSERT OR UPDATE ON supplier_bills FOR EACH ROW EXECUTE FUNCTION reject_duplicate_supplier_invoice_no()")

def downgrade() -> None:
    bind=op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS trg_supplier_invoice_no_unique ON supplier_bills")
        op.execute("DROP FUNCTION IF EXISTS reject_duplicate_supplier_invoice_no()")
        op.execute("DROP TRIGGER IF EXISTS trg_supplier_bill_item_claim ON supplier_bill_items")
        op.execute("DROP FUNCTION IF EXISTS reject_duplicate_active_purchase_result_claim()")
        op.execute("DROP SEQUENCE IF EXISTS supplier_bill_document_seq")
    op.drop_table("supplier_payments");op.drop_table("supplier_bill_items");op.drop_table("supplier_bills")
