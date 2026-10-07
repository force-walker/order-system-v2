"""Canonicalize persisted UOM values.

Revision ID: 2026100602
Revises: 2026100601

This migration changes UOM strings only; quantities and document identities are
not modified.  Legacy ``count`` is the former generic count code used by this
application and is migrated to the canonical ``piece`` code.
"""

from alembic import op
import sqlalchemy as sa


revision = "2026100602"
down_revision = "2026100601"
branch_labels = None
depends_on = None


UOM_COLUMNS = (
    ("products", "order_uom", False),
    ("products", "purchase_uom", False),
    ("products", "invoice_uom", False),
    ("supplier_allocations", "final_uom", True),
    ("purchase_results", "purchased_uom", False),
    ("invoice_items", "billable_uom", False),
    ("delivery_items", "delivered_uom", False),
)

ALIASES = {
    "kg": "kg",
    "pc": "piece",
    "piece": "piece",
    "count": "piece",
    "ctn": "case",
    "case": "case",
}


def _canonical_expression(column: str) -> str:
    return (
        f"CASE lower(trim({column})) "
        "WHEN 'kg' THEN 'kg' "
        "WHEN 'pc' THEN 'piece' "
        "WHEN 'piece' THEN 'piece' "
        "WHEN 'count' THEN 'piece' "
        "WHEN 'ctn' THEN 'case' "
        "WHEN 'case' THEN 'case' END"
    )


def upgrade() -> None:
    bind = op.get_bind()
    for table, column, nullable in UOM_COLUMNS:
        null_clause = f"{column} IS NOT NULL AND " if nullable else ""
        unknown = bind.execute(sa.text(
            f"SELECT DISTINCT {column} FROM {table} "
            f"WHERE {null_clause}lower(trim({column})) NOT IN "
            "('kg', 'pc', 'piece', 'count', 'ctn', 'case')"
        )).scalars().all()
        if unknown:
            raise RuntimeError(f"unknown UOM values in {table}.{column}: {unknown}")

    for table, column, nullable in UOM_COLUMNS:
        where = f" WHERE {column} IS NOT NULL" if nullable else ""
        op.execute(f"UPDATE {table} SET {column} = {_canonical_expression(column)}{where}")

    if bind.dialect.name == "postgresql":
        for table, column, nullable in UOM_COLUMNS:
            allowed = f"{column} IS NULL OR " if nullable else ""
            op.create_check_constraint(
                f"ck_{table}_{column}_canonical",
                table,
                f"{allowed}{column} IN ('piece', 'case', 'kg')",
            )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for table, column, _nullable in reversed(UOM_COLUMNS):
            op.drop_constraint(f"ck_{table}_{column}_canonical", table, type_="check")
    # Canonical values intentionally remain canonical; the former spelling is
    # not business data and cannot be reconstructed safely.
