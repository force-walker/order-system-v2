"""Enforce non-empty documents and immutable business numbering on PostgreSQL."""

from alembic import op
import sqlalchemy as sa


revision = "2026092005"
down_revision = "2026092004"
branch_labels = None
depends_on = None


def _assert_nonempty(bind, parent: str, child: str, fk: str) -> None:
    count = int(
        bind.execute(
            sa.text(
                f"SELECT COUNT(*) FROM {parent} p WHERE NOT EXISTS "
                f"(SELECT 1 FROM {child} c WHERE c.{fk}=p.id)"
            )
        ).scalar_one()
    )
    if count:
        raise RuntimeError(f"cannot enforce non-empty {parent}: {count} headers have no detail")


def upgrade():
    bind = op.get_bind()
    for parent, child, fk in (
        ("orders", "order_items", "order_id"),
        ("deliveries", "delivery_items", "delivery_id"),
        ("invoices", "invoice_items", "invoice_id"),
    ):
        _assert_nonempty(bind, parent, child, fk)

    if bind.dialect.name != "postgresql":
        return

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
    for table in ("orders", "deliveries", "invoices"):
        op.execute(
            f"CREATE TRIGGER trg_{table}_immutable_document_seq BEFORE UPDATE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION reject_business_number_change()"
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
    op.execute(
        "CREATE TRIGGER trg_invoices_immutable_official_document_seq BEFORE UPDATE ON invoices "
        "FOR EACH ROW EXECUTE FUNCTION reject_official_invoice_sequence_change()"
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION reject_line_identity_change() RETURNS trigger AS $$
        BEGIN
          IF NEW.line_no IS DISTINCT FROM OLD.line_no
             OR NEW.line_ref IS DISTINCT FROM OLD.line_ref
             OR (to_jsonb(NEW) ->> TG_ARGV[0]) IS DISTINCT FROM (to_jsonb(OLD) ->> TG_ARGV[0]) THEN
            RAISE EXCEPTION 'line parent, line_no and line_ref are immutable';
          END IF;
          RETURN NEW;
        END; $$ LANGUAGE plpgsql;
        """
    )
    for table, parent_fk in (
        ("order_items", "order_id"),
        ("delivery_items", "delivery_id"),
        ("invoice_items", "invoice_id"),
    ):
        op.execute(
            f"CREATE TRIGGER trg_{table}_immutable_line_identity BEFORE UPDATE ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION reject_line_identity_change('{parent_fk}')"
        )

    for parent, child, fk in (
        ("orders", "order_items", "order_id"),
        ("deliveries", "delivery_items", "delivery_id"),
        ("invoices", "invoice_items", "invoice_id"),
    ):
        fn = f"assert_{parent}_has_detail_after_child_change"
        header_fn = f"assert_{parent}_has_detail_after_header_change"
        op.execute(
            f"""
            CREATE OR REPLACE FUNCTION {fn}() RETURNS trigger AS $$
            BEGIN
              IF TG_OP IN ('DELETE', 'UPDATE')
                 AND EXISTS (SELECT 1 FROM {parent} WHERE id=OLD.{fk})
                 AND NOT EXISTS (SELECT 1 FROM {child} WHERE {fk}=OLD.{fk}) THEN
                RAISE EXCEPTION '{parent} header must have at least one detail';
              END IF;
              IF TG_OP IN ('INSERT', 'UPDATE')
                 AND EXISTS (SELECT 1 FROM {parent} WHERE id=NEW.{fk})
                 AND NOT EXISTS (SELECT 1 FROM {child} WHERE {fk}=NEW.{fk}) THEN
                RAISE EXCEPTION '{parent} header must have at least one detail';
              END IF;
              RETURN COALESCE(NEW, OLD);
            END; $$ LANGUAGE plpgsql;
            """
        )
        op.execute(
            f"""
            CREATE OR REPLACE FUNCTION {header_fn}() RETURNS trigger AS $$
            BEGIN
              IF NOT EXISTS (SELECT 1 FROM {child} WHERE {fk}=NEW.id) THEN
                RAISE EXCEPTION '{parent} header must have at least one detail';
              END IF;
              RETURN NEW;
            END; $$ LANGUAGE plpgsql;
            """
        )
        op.execute(
            f"CREATE CONSTRAINT TRIGGER trg_{child}_nonempty_parent "
            f"AFTER INSERT OR UPDATE OR DELETE ON {child} DEFERRABLE INITIALLY DEFERRED "
            f"FOR EACH ROW EXECUTE FUNCTION {fn}()"
        )
        op.execute(
            f"CREATE CONSTRAINT TRIGGER trg_{parent}_nonempty_header "
            f"AFTER INSERT OR UPDATE ON {parent} DEFERRABLE INITIALLY DEFERRED "
            f"FOR EACH ROW EXECUTE FUNCTION {header_fn}()"
        )


def downgrade():
    if op.get_bind().dialect.name != "postgresql":
        return
    for parent, child, _fk in (
        ("orders", "order_items", "order_id"),
        ("deliveries", "delivery_items", "delivery_id"),
        ("invoices", "invoice_items", "invoice_id"),
    ):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{child}_nonempty_parent ON {child}")
        op.execute(f"DROP TRIGGER IF EXISTS trg_{parent}_nonempty_header ON {parent}")
        op.execute(f"DROP FUNCTION IF EXISTS assert_{parent}_has_detail_after_child_change()")
        op.execute(f"DROP FUNCTION IF EXISTS assert_{parent}_has_detail_after_header_change()")
    for table in ("order_items", "delivery_items", "invoice_items"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_immutable_line_identity ON {table}")
    op.execute("DROP FUNCTION IF EXISTS reject_line_identity_change()")
    for table in ("orders", "deliveries", "invoices"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_immutable_document_seq ON {table}")
    op.execute("DROP FUNCTION IF EXISTS reject_business_number_change()")
    op.execute("DROP TRIGGER IF EXISTS trg_invoices_immutable_official_document_seq ON invoices")
    op.execute("DROP FUNCTION IF EXISTS reject_official_invoice_sequence_change()")
