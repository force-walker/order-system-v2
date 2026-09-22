"""Enforce Detail line-reference consistency with its parent Header.

Revision ID: 2026092008
Revises: 2026092007
"""

from alembic import op
import sqlalchemy as sa


revision = "2026092008"
down_revision = "2026092007"
branch_labels = None
depends_on = None


RULES = (
    ("order_items", "orders", "order_id", "ODL"),
    ("delivery_items", "deliveries", "delivery_id", "DLI"),
    ("invoice_items", "invoices", "invoice_id", "IVL"),
)


def _expected_line_ref(prefix: str, parent_alias: str, child_alias: str) -> str:
    return (
        f"'{prefix}-' || "
        f"lpad({parent_alias}.document_seq::text, "
        f"GREATEST(8, length({parent_alias}.document_seq::text)), '0') || '-' || "
        f"lpad({child_alias}.line_no::text, "
        f"GREATEST(4, length({child_alias}.line_no::text)), '0')"
    )


def _assert_existing_line_references(
    bind, child: str, parent: str, fk: str, prefix: str
) -> None:
    expected = _expected_line_ref(prefix, "p", "c")
    count = int(
        bind.execute(
            sa.text(
                f"SELECT COUNT(*) FROM {child} c "
                f"JOIN {parent} p ON p.id=c.{fk} "
                f"WHERE c.line_ref IS DISTINCT FROM ({expected})"
            )
        ).scalar_one()
    )
    if count:
        raise RuntimeError(
            f"cannot enforce {child} line reference consistency: "
            f"{count} existing rows are inconsistent"
        )


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    # Do not silently rewrite issued business identifiers. Migration stops
    # before installing any trigger if a backfilled value is inconsistent.
    for child, parent, fk, prefix in RULES:
        _assert_existing_line_references(bind, child, parent, fk, prefix)

    for child, parent, fk, prefix in RULES:
        function_name = f"enforce_{child}_line_reference_consistency"
        trigger_name = f"trg_000_{child}_line_reference_consistency"
        op.execute(
            f"""
            CREATE FUNCTION {function_name}() RETURNS trigger AS $$
            DECLARE
              parent_document_seq bigint;
              expected_line_ref text;
            BEGIN
              SELECT document_seq INTO parent_document_seq
                FROM {parent} WHERE id=NEW.{fk};

              -- Missing parents remain the foreign key's responsibility.
              IF NOT FOUND THEN
                RETURN NEW;
              END IF;

              expected_line_ref := '{prefix}-' ||
                lpad(parent_document_seq::text,
                     GREATEST(8, length(parent_document_seq::text)), '0') || '-' ||
                lpad(NEW.line_no::text,
                     GREATEST(4, length(NEW.line_no::text)), '0');

              IF NEW.line_ref IS DISTINCT FROM expected_line_ref THEN
                RAISE EXCEPTION '{child}.line_ref must match parent document_seq and line_no'
                  USING ERRCODE = '23514';
              END IF;
              RETURN NEW;
            END; $$ LANGUAGE plpgsql;
            """
        )
        op.execute(
            f"CREATE TRIGGER {trigger_name} BEFORE INSERT OR UPDATE ON {child} "
            f"FOR EACH ROW EXECUTE FUNCTION {function_name}()"
        )


def downgrade():
    if op.get_bind().dialect.name != "postgresql":
        return
    for child, _parent, _fk, _prefix in reversed(RULES):
        function_name = f"enforce_{child}_line_reference_consistency"
        trigger_name = f"trg_000_{child}_line_reference_consistency"
        op.execute(f"DROP TRIGGER IF EXISTS {trigger_name} ON {child}")
        op.execute(f"DROP FUNCTION IF EXISTS {function_name}()")
