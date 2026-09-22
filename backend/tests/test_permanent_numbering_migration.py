"""Backfill migration preservation tests in an isolated PostgreSQL schema."""

import importlib.util
import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError


def _migration(revision: str):
    path = next((Path(__file__).parents[1] / "alembic/versions").glob(f"{revision}_*.py"))
    spec = importlib.util.spec_from_file_location(f"migration_{revision}", path)
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
        schema = "permanent_numbering_migration_" + uuid4().hex
        try:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            yield connection
        finally:
            transaction.rollback()
    engine.dispose()


def _create_legacy_tables(connection) -> None:
    connection.execute(text("CREATE TABLE orders (id varchar(36) PRIMARY KEY, legacy_id integer, order_no varchar(64), created_at timestamp NOT NULL)"))
    connection.execute(text("CREATE TABLE order_items (id varchar(36) PRIMARY KEY, legacy_id integer, order_id varchar(36) NOT NULL REFERENCES orders(id), order_line_no varchar(32), created_at timestamp NOT NULL)"))
    connection.execute(text("CREATE TABLE deliveries (id varchar(36) PRIMARY KEY, delivery_no varchar(32), created_at timestamp NOT NULL)"))
    connection.execute(text("CREATE TABLE delivery_items (id varchar(36) PRIMARY KEY, delivery_id varchar(36) NOT NULL REFERENCES deliveries(id), delivery_line_no varchar(32), created_at timestamp NOT NULL)"))
    connection.execute(text("CREATE TABLE invoices (id varchar(36) PRIMARY KEY, legacy_id integer, delivery_no varchar(32), invoice_draft_no varchar(32), official_invoice_no varchar(32), created_at timestamp NOT NULL)"))
    connection.execute(text("CREATE TABLE invoice_items (id varchar(36) PRIMARY KEY, legacy_id integer, invoice_id varchar(36) NOT NULL REFERENCES invoices(id), invoice_line_no varchar(32), created_at timestamp NOT NULL)"))


def test_backfill_preserves_uuid_and_legacy_number_strings(pg):
    _create_legacy_tables(pg)
    order_id = str(uuid4())
    item_id = str(uuid4())
    old_order_no = "ORD-20260919-00001"
    old_line_no = "ODL-00001-0001"
    pg.execute(
        text("INSERT INTO orders VALUES (:id, 41, :number, '2026-09-19 10:00:00')"),
        {"id": order_id, "number": old_order_no},
    )
    pg.execute(
        text("INSERT INTO order_items VALUES (:id, 91, :order_id, :number, '2026-09-19 10:01:00')"),
        {"id": item_id, "order_id": order_id, "number": old_line_no},
    )

    with Operations.context(MigrationContext.configure(pg)):
        for revision in (
            "2026092002",
            "2026092003",
            "2026092004",
            "2026092005",
            "2026092006",
            "2026092007",
            "2026092008",
        ):
            _migration(revision).upgrade()

    order = pg.execute(
        text("SELECT id, legacy_id, order_no, document_seq, next_line_no FROM orders WHERE id=:id"),
        {"id": order_id},
    ).one()
    item = pg.execute(
        text("SELECT id, legacy_id, order_line_no, line_no, line_ref FROM order_items WHERE id=:id"),
        {"id": item_id},
    ).one()
    assert order == (order_id, 41, old_order_no, 1, 20)
    assert item == (item_id, 91, old_line_no, 10, "ODL-00000001-0010")
    assert pg.scalar(text("SELECT last_value FROM order_document_seq")) == 1
    assert pg.scalar(text("SELECT last_value FROM orders_legacy_id_seq")) == 41
    assert pg.scalar(text("SELECT last_value FROM order_items_legacy_id_seq")) == 91


def test_business_number_consistency_on_insert_update_and_legacy_backfill(pg):
    _create_legacy_tables(pg)
    legacy_order_id = str(uuid4())
    legacy_item_id = str(uuid4())
    pg.execute(
        text("INSERT INTO orders VALUES (:id, 1, 'ORD-20260919-00001', '2026-09-19 10:00:00')"),
        {"id": legacy_order_id},
    )
    pg.execute(
        text(
            "INSERT INTO order_items VALUES "
            "(:id, 1, :order_id, 'ODL-00001-0001', '2026-09-19 10:01:00')"
        ),
        {"id": legacy_item_id, "order_id": legacy_order_id},
    )

    with Operations.context(MigrationContext.configure(pg)):
        for revision in (
            "2026092002",
            "2026092003",
            "2026092004",
            "2026092005",
            "2026092006",
            "2026092007",
            "2026092008",
        ):
            _migration(revision).upgrade()

    # Existing legacy formats remain unchanged and unrelated updates are valid.
    pg.execute(text("UPDATE orders SET next_line_no=next_line_no WHERE id=:id"), {"id": legacy_order_id})
    assert pg.scalar(text("SELECT order_no FROM orders WHERE id=:id"), {"id": legacy_order_id}) == "ORD-20260919-00001"

    invalid_inserts = (
        (
            "INSERT INTO orders (id, document_seq, next_line_no, order_no, created_at) "
            "VALUES ('bad-order', 25, 10, 'ORD-99999999', now())",
            "order_no must match document_seq",
        ),
        (
            "INSERT INTO deliveries (id, document_seq, next_line_no, delivery_no, created_at) "
            "VALUES ('bad-delivery', 12, 10, 'DEL-00000099', now())",
            "delivery_no must match document_seq",
        ),
        (
            "INSERT INTO invoices (id, document_seq, next_line_no, invoice_draft_no, created_at) "
            "VALUES ('bad-invoice', 31, 10, 'IVD-99999999', now())",
            "invoice_draft_no must match document_seq",
        ),
    )
    for statement, message in invalid_inserts:
        with pytest.raises(DBAPIError) as caught, pg.begin_nested():
            pg.execute(text(statement))
        assert getattr(caught.value.orig, "sqlstate", None) == "23514"
        assert message in str(caught.value.orig)

    pg.execute(text(
        "INSERT INTO orders (id, document_seq, next_line_no, order_no, created_at) "
        "VALUES ('valid-order', 25, 20, 'ORD-00000025', now())"
    ))
    pg.execute(text(
        "INSERT INTO order_items (id, order_id, line_no, line_ref, created_at) "
        "VALUES ('valid-order-item', 'valid-order', 10, 'ODL-00000025-0010', now())"
    ))
    pg.execute(text(
        "INSERT INTO deliveries (id, document_seq, next_line_no, delivery_no, created_at) "
        "VALUES ('valid-delivery', 12, 20, 'DEL-00000012', now())"
    ))
    pg.execute(text(
        "INSERT INTO delivery_items (id, delivery_id, line_no, line_ref, created_at) "
        "VALUES ('valid-delivery-item', 'valid-delivery', 10, 'DLI-00000012-0010', now())"
    ))
    pg.execute(text(
        "INSERT INTO invoices (id, document_seq, next_line_no, invoice_draft_no, created_at) "
        "VALUES ('valid-invoice', 31, 20, 'IVD-00000031', now())"
    ))
    pg.execute(text(
        "INSERT INTO invoice_items (id, invoice_id, line_no, line_ref, created_at) "
        "VALUES ('valid-invoice-item', 'valid-invoice', 10, 'IVL-00000031-0010', now())"
    ))
    pg.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))
    pg.execute(text("SET CONSTRAINTS ALL DEFERRED"))
    assert pg.scalar(text("SELECT count(*) FROM orders WHERE id='valid-order'")) == 1
    assert pg.scalar(text("SELECT count(*) FROM deliveries WHERE id='valid-delivery'")) == 1
    assert pg.scalar(text("SELECT count(*) FROM invoices WHERE id='valid-invoice'")) == 1
    pg.execute(text(
        "UPDATE orders SET order_no='ORD-00000025' WHERE id='valid-order'"
    ))
    pg.execute(text(
        "UPDATE deliveries SET delivery_no='DEL-00000012' WHERE id='valid-delivery'"
    ))
    pg.execute(text(
        "UPDATE invoices SET invoice_draft_no='IVD-00000031' WHERE id='valid-invoice'"
    ))

    invalid_updates = (
        (
            "UPDATE orders SET order_no='ORD-99999999' WHERE id='valid-order'",
            "order_no must match document_seq",
        ),
        (
            "UPDATE deliveries SET delivery_no='DEL-00000099' WHERE id='valid-delivery'",
            "delivery_no must match document_seq",
        ),
        (
            "UPDATE invoices SET invoice_draft_no='IVD-99999999' WHERE id='valid-invoice'",
            "invoice_draft_no must match document_seq",
        ),
    )
    for statement, message in invalid_updates:
        with pytest.raises(DBAPIError) as caught, pg.begin_nested():
            pg.execute(text(statement))
        assert getattr(caught.value.orig, "sqlstate", None) == "23514"
        assert message in str(caught.value.orig)
