"""Harden permanent numbering and non-empty aggregate invariants.

Revision ID: 2026092006
Revises: 2026092005
"""

from alembic import op


revision = "2026092006"
down_revision = "2026092005"
branch_labels = None
depends_on = None


AGGREGATES = (
    ("orders", "order_items", "order_id"),
    ("deliveries", "delivery_items", "delivery_id"),
    ("invoices", "invoice_items", "invoice_id"),
)


def _install_nonempty_functions(*, lock_parent: bool) -> None:
    for parent, child, fk in AGGREGATES:
        fn = f"assert_{parent}_has_detail_after_child_change"
        lock_old = f"PERFORM 1 FROM {parent} WHERE id=OLD.{fk} FOR UPDATE;" if lock_parent else ""
        lock_new = f"PERFORM 1 FROM {parent} WHERE id=NEW.{fk} FOR UPDATE;" if lock_parent else ""
        op.execute(
            f"""
            CREATE OR REPLACE FUNCTION {fn}() RETURNS trigger AS $$
            BEGIN
              IF TG_OP IN ('DELETE', 'UPDATE') THEN
                {lock_old}
                IF FOUND
                   AND NOT EXISTS (SELECT 1 FROM {child} WHERE {fk}=OLD.{fk}) THEN
                  RAISE EXCEPTION '{parent} header must have at least one detail';
                END IF;
              END IF;
              IF TG_OP IN ('INSERT', 'UPDATE') THEN
                {lock_new}
                IF FOUND
                   AND NOT EXISTS (SELECT 1 FROM {child} WHERE {fk}=NEW.{fk}) THEN
                  RAISE EXCEPTION '{parent} header must have at least one detail';
                END IF;
              END IF;
              RETURN COALESCE(NEW, OLD);
            END; $$ LANGUAGE plpgsql;
            """
        )


def _install_2005_business_number_functions() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION reject_business_number_change() RETURNS trigger AS $$
        BEGIN
          IF NEW.document_seq IS DISTINCT FROM OLD.document_seq THEN
            RAISE EXCEPTION 'document_seq is immutable';
          END IF;
          RETURN NEW;
        END; $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION reject_official_invoice_sequence_change() RETURNS trigger AS $$
        BEGIN
          IF OLD.official_document_seq IS NOT NULL
             AND NEW.official_document_seq IS DISTINCT FROM OLD.official_document_seq THEN
            RAISE EXCEPTION 'official_document_seq is immutable once allocated';
          END IF;
          RETURN NEW;
        END; $$ LANGUAGE plpgsql;
        """
    )


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        return

    # Deferred child checks serialize on their parent Header. This closes the
    # write-skew window where two transactions could each delete one of the
    # final two Detail rows while still seeing the other's uncommitted row.
    _install_nonempty_functions(lock_parent=True)

    op.execute(
        """
        CREATE OR REPLACE FUNCTION reject_business_number_change() RETURNS trigger AS $$
        BEGIN
          IF NEW.document_seq IS DISTINCT FROM OLD.document_seq THEN
            RAISE EXCEPTION 'document_seq is immutable';
          END IF;

          IF TG_TABLE_NAME = 'orders'
             AND (to_jsonb(NEW) ->> 'order_no') IS DISTINCT FROM
                 (to_jsonb(OLD) ->> 'order_no') THEN
            RAISE EXCEPTION 'order_no is immutable';
          END IF;

          IF TG_TABLE_NAME = 'deliveries'
             AND (to_jsonb(NEW) ->> 'delivery_no') IS DISTINCT FROM
                 (to_jsonb(OLD) ->> 'delivery_no') THEN
            RAISE EXCEPTION 'delivery_no is immutable';
          END IF;

          IF TG_TABLE_NAME = 'invoices' THEN
            IF (to_jsonb(OLD) ->> 'invoice_draft_no') IS NOT NULL
               AND (to_jsonb(NEW) ->> 'invoice_draft_no') IS DISTINCT FROM
                   (to_jsonb(OLD) ->> 'invoice_draft_no') THEN
              RAISE EXCEPTION 'invoice_draft_no is immutable once allocated';
            END IF;
            IF (to_jsonb(OLD) ->> 'invoice_draft_no') IS NULL
               AND (to_jsonb(NEW) ->> 'invoice_draft_no') IS NOT NULL
               AND (to_jsonb(NEW) ->> 'invoice_draft_no') IS DISTINCT FROM
                   ('IVD-' || lpad(NEW.document_seq::text, 8, '0')) THEN
              RAISE EXCEPTION 'invoice_draft_no must match document_seq';
            END IF;
          END IF;

          RETURN NEW;
        END; $$ LANGUAGE plpgsql;
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION reject_official_invoice_sequence_change() RETURNS trigger AS $$
        BEGIN
          IF OLD.official_document_seq IS NOT NULL OR OLD.official_invoice_no IS NOT NULL THEN
            IF NEW.official_document_seq IS DISTINCT FROM OLD.official_document_seq
               OR NEW.official_invoice_no IS DISTINCT FROM OLD.official_invoice_no THEN
              RAISE EXCEPTION 'official invoice sequence and number are immutable once allocated';
            END IF;
          ELSIF NEW.official_document_seq IS NOT NULL OR NEW.official_invoice_no IS NOT NULL THEN
            IF NEW.official_document_seq IS NULL OR NEW.official_invoice_no IS NULL THEN
              RAISE EXCEPTION 'official invoice sequence and number must be allocated together';
            END IF;
            IF NEW.official_invoice_no IS DISTINCT FROM
               ('INV-' || lpad(NEW.official_document_seq::text, 8, '0')) THEN
              RAISE EXCEPTION 'official_invoice_no must match official_document_seq';
            END IF;
          END IF;
          RETURN NEW;
        END; $$ LANGUAGE plpgsql;
        """
    )


def downgrade():
    if op.get_bind().dialect.name != "postgresql":
        return
    _install_nonempty_functions(lock_parent=False)
    _install_2005_business_number_functions()
