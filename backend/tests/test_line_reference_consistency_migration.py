"""PostgreSQL tests for migration 2026092008 line-reference invariants."""

import importlib.util
import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError


def _migration():
    path = next(
        (Path(__file__).parents[1] / "alembic/versions").glob(
            "2026092008_enforce_line_reference_consistency.py"
        )
    )
    spec = importlib.util.spec_from_file_location("migration_2026092008", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def pg():
    url = os.getenv("TEST_POSTGRES_URL")
    if not url:
        pytest.skip("TEST_POSTGRES_URL required for PostgreSQL migration regression")
    engine = create_engine(url)
    with engine.connect() as connection:
        transaction = connection.begin()
        schema = "line_reference_consistency_" + uuid4().hex
        try:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            yield connection
        finally:
            transaction.rollback()
    engine.dispose()


def _create_tables(pg) -> None:
    for parent in ("orders", "deliveries", "invoices"):
        pg.execute(
            text(
                f"CREATE TABLE {parent} ("
                "id varchar(36) PRIMARY KEY, document_seq bigint NOT NULL)"
            )
        )
    for child, parent, fk in (
        ("order_items", "orders", "order_id"),
        ("delivery_items", "deliveries", "delivery_id"),
        ("invoice_items", "invoices", "invoice_id"),
    ):
        pg.execute(
            text(
                f"CREATE TABLE {child} ("
                "id varchar(36) PRIMARY KEY, "
                f"{fk} varchar(36) NOT NULL REFERENCES {parent}(id), "
                "line_no integer NOT NULL CHECK (line_no > 0), "
                "line_ref varchar(64) NOT NULL UNIQUE, "
                f"UNIQUE ({fk}, line_no))"
            )
        )


def _install_migration(pg) -> None:
    with Operations.context(MigrationContext.configure(pg)):
        _migration().upgrade()


def _assert_check_violation(pg, statement: str) -> None:
    with pytest.raises(DBAPIError) as caught, pg.begin_nested():
        pg.execute(text(statement))
    assert getattr(caught.value.orig, "sqlstate", None) == "23514"


@pytest.mark.parametrize(
    ("child", "parent", "fk", "prefix", "document_seq"),
    (
        ("order_items", "orders", "order_id", "ODL", 25),
        ("delivery_items", "deliveries", "delivery_id", "DLI", 12),
        ("invoice_items", "invoices", "invoice_id", "IVL", 31),
    ),
)
def test_insert_enforces_parent_sequence_line_number_and_prefix(
    pg, child, parent, fk, prefix, document_seq
):
    _create_tables(pg)
    parent_id = f"{parent}-parent"
    pg.execute(
        text(f"INSERT INTO {parent} (id, document_seq) VALUES (:id, :sequence)"),
        {"id": parent_id, "sequence": document_seq},
    )
    _install_migration(pg)

    pg.execute(
        text(
            f"INSERT INTO {child} (id, {fk}, line_no, line_ref) "
            "VALUES ('valid-10', :parent_id, 10, :line_ref)"
        ),
        {
            "parent_id": parent_id,
            "line_ref": f"{prefix}-{document_seq:08d}-0010",
        },
    )
    # Business line numbers are positive and immutable, not restricted to
    # multiples of ten. A correctly formatted inserted line 15 is valid.
    pg.execute(
        text(
            f"INSERT INTO {child} (id, {fk}, line_no, line_ref) "
            "VALUES ('valid-15', :parent_id, 15, :line_ref)"
        ),
        {
            "parent_id": parent_id,
            "line_ref": f"{prefix}-{document_seq:08d}-0015",
        },
    )

    _assert_check_violation(
        pg,
        f"INSERT INTO {child} (id, {fk}, line_no, line_ref) "
        f"VALUES ('bad-sequence', '{parent_id}', 20, '{prefix}-99999999-0020')",
    )
    _assert_check_violation(
        pg,
        f"INSERT INTO {child} (id, {fk}, line_no, line_ref) "
        f"VALUES ('bad-line', '{parent_id}', 30, '{prefix}-{document_seq:08d}-0040')",
    )
    wrong_prefix = "IVL" if prefix != "IVL" else "ODL"
    _assert_check_violation(
        pg,
        f"INSERT INTO {child} (id, {fk}, line_no, line_ref) "
        f"VALUES ('bad-prefix', '{parent_id}', 40, "
        f"'{wrong_prefix}-{document_seq:08d}-0040')",
    )


def test_update_to_inconsistent_line_reference_is_rejected(pg):
    _create_tables(pg)
    pg.execute(text("INSERT INTO orders (id, document_seq) VALUES ('order-1', 25)"))
    pg.execute(
        text(
            "INSERT INTO order_items (id, order_id, line_no, line_ref) "
            "VALUES ('item-1', 'order-1', 10, 'ODL-00000025-0010')"
        )
    )
    _install_migration(pg)

    _assert_check_violation(
        pg,
        "UPDATE order_items SET line_ref='ODL-00000099-0010' WHERE id='item-1'",
    )


def test_migration_accepts_consistent_existing_rows(pg):
    _create_tables(pg)
    for parent, document_seq in (("orders", 25), ("deliveries", 12), ("invoices", 31)):
        pg.execute(
            text(f"INSERT INTO {parent} (id, document_seq) VALUES (:id, :sequence)"),
            {"id": f"{parent}-parent", "sequence": document_seq},
        )
    for child, fk, parent_id, line_ref in (
        ("order_items", "order_id", "orders-parent", "ODL-00000025-0010"),
        ("delivery_items", "delivery_id", "deliveries-parent", "DLI-00000012-0010"),
        ("invoice_items", "invoice_id", "invoices-parent", "IVL-00000031-0010"),
    ):
        pg.execute(
            text(
                f"INSERT INTO {child} (id, {fk}, line_no, line_ref) "
                "VALUES (:id, :parent_id, 10, :line_ref)"
            ),
            {"id": f"{child}-item", "parent_id": parent_id, "line_ref": line_ref},
        )

    _install_migration(pg)


def test_migration_stops_without_rewriting_inconsistent_existing_row(pg):
    _create_tables(pg)
    pg.execute(text("INSERT INTO orders (id, document_seq) VALUES ('order-1', 25)"))
    pg.execute(
        text(
            "INSERT INTO order_items (id, order_id, line_no, line_ref) "
            "VALUES ('item-1', 'order-1', 10, 'ODL-99999999-0010')"
        )
    )

    with pytest.raises(RuntimeError, match="1 existing rows are inconsistent"):
        _install_migration(pg)

    assert (
        pg.scalar(text("SELECT line_ref FROM order_items WHERE id='item-1'"))
        == "ODL-99999999-0010"
    )
    assert (
        pg.scalar(
            text(
                "SELECT count(*) FROM pg_trigger "
                "WHERE tgname LIKE 'trg_000_%_line_reference_consistency'"
            )
        )
        == 0
    )
