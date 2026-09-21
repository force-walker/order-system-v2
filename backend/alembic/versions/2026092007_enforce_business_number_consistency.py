"""Enforce Header business-number consistency for new and changed values.

Revision ID: 2026092007
Revises: 2026092006
"""

from alembic import op


revision = "2026092007"
down_revision = "2026092006"
branch_labels = None
depends_on = None


RULES = (
    ("orders", "order_no", "ORD"),
    ("deliveries", "delivery_no", "DEL"),
    ("invoices", "invoice_draft_no", "IVD"),
)


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        return

    for table, number_column, prefix in RULES:
        function_name = f"enforce_{table}_business_number_consistency"
        trigger_name = f"trg_{table}_business_number_consistency"
        op.execute(
            f"""
            CREATE FUNCTION {function_name}() RETURNS trigger AS $$
            DECLARE
              expected_number text;
            BEGIN
              IF TG_OP = 'INSERT'
                 OR NEW.document_seq IS DISTINCT FROM OLD.document_seq
                 OR NEW.{number_column} IS DISTINCT FROM OLD.{number_column} THEN
                expected_number := '{prefix}-' || lpad(NEW.document_seq::text, 8, '0');
                IF NEW.{number_column} IS DISTINCT FROM expected_number THEN
                  RAISE EXCEPTION '{number_column} must match document_seq'
                    USING ERRCODE = '23514';
                END IF;
              END IF;
              RETURN NEW;
            END; $$ LANGUAGE plpgsql;
            """
        )
        op.execute(
            f"CREATE TRIGGER {trigger_name} BEFORE INSERT OR UPDATE ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION {function_name}()"
        )


def downgrade():
    if op.get_bind().dialect.name != "postgresql":
        return
    for table, _number_column, _prefix in reversed(RULES):
        function_name = f"enforce_{table}_business_number_consistency"
        trigger_name = f"trg_{table}_business_number_consistency"
        op.execute(f"DROP TRIGGER IF EXISTS {trigger_name} ON {table}")
        op.execute(f"DROP FUNCTION IF EXISTS {function_name}()")
