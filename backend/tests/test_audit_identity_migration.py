"""PostgreSQL regression tests use rollback-only isolated schemas, never public data.

Run with TEST_POSTGRES_URL pointing to a disposable/test PostgreSQL database.
"""
import importlib.util
import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


def migration():
    path = Path(__file__).parents[1] / "alembic/versions/2026091801_restore_audit_log_identity.py"
    spec = importlib.util.spec_from_file_location("audit_identity_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def pg():
    url = os.getenv("TEST_POSTGRES_URL")
    if not url:
        pytest.skip("TEST_POSTGRES_URL required for PostgreSQL regression")
    engine = create_engine(url)
    assert engine.dialect.name == "postgresql"
    with engine.connect() as connection:
        transaction = connection.begin()
        schema = "audit_repair_test_" + uuid4().hex
        try:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            with Operations.context(MigrationContext.configure(connection)):
                yield connection
        finally:
            transaction.rollback()  # Includes schema, tables, sequences and test data.
    engine.dispose()


@pytest.mark.parametrize("existing", [False, True])
def test_missing_generator_reproduced_and_repaired(pg, existing):
    pg.execute(text("CREATE TABLE audit_logs (id INTEGER PRIMARY KEY, marker TEXT)"))
    if existing:
        pg.execute(text("INSERT INTO audit_logs VALUES (42, 'preserve')"))
    with pytest.raises(IntegrityError):
        with pg.begin_nested():
            pg.execute(text("INSERT INTO audit_logs (marker) VALUES ('before')"))
    migration().upgrade()
    expected = 43 if existing else 1
    assert pg.scalar(text("INSERT INTO audit_logs (marker) VALUES ('after') RETURNING id")) == expected
    migration().upgrade()  # Must not rewind a working sequence.
    assert pg.scalar(text("INSERT INTO audit_logs (marker) VALUES ('again') RETURNING id")) == expected + 1
    migration().downgrade()
    assert pg.scalar(text("INSERT INTO audit_logs (marker) VALUES ('downgraded') RETURNING id")) == expected + 2
    if existing:
        assert pg.scalar(text("SELECT marker FROM audit_logs WHERE id=42")) == "preserve"


def test_existing_serial_generator_preserved(pg):
    pg.execute(text("CREATE TABLE audit_logs (id SERIAL PRIMARY KEY)"))
    pg.execute(text("ALTER SEQUENCE audit_logs_id_seq RESTART WITH 99"))
    migration().upgrade()
    assert pg.scalar(text("INSERT INTO audit_logs DEFAULT VALUES RETURNING id")) == 99


def test_postgres_order_create_list_cancel_with_audit(pg):
    from app.db.base import Base
    from app.models.entities import AuditLog, Customer
    from app.api.routes_orders import create_order, list_orders, bulk_cancel_orders
    from app.schemas.order import OrderCreateRequest, OrderBulkCancelRequest

    Base.metadata.create_all(pg)
    # Reproduce the actual deployed schema produced by the old UUID migration.
    pg.execute(text("ALTER TABLE audit_logs ALTER COLUMN id DROP DEFAULT"))
    migration().upgrade()
    with Session(bind=pg, join_transaction_mode="create_savepoint") as db:
        customer = Customer(customer_code="repair-test", name="Test only")
        db.add(customer)
        db.commit()
        order = create_order(OrderCreateRequest(customer_id=customer.id), db)
        assert order.id in {o.id for o in list_orders(stale_delivery_only=False, db=db)}
        result = bulk_cancel_orders(OrderBulkCancelRequest(
            order_ids=[order.id], cancel_reason_code="customer_request"
        ), db)
        assert result.succeeded == 1
        assert db.query(AuditLog).filter(AuditLog.entity_id == order.id).count() == 2


def test_sqlite_unchanged():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE audit_logs (id INTEGER PRIMARY KEY)"))
        with Operations.context(MigrationContext.configure(connection)):
            migration().upgrade()
        connection.execute(text("INSERT INTO audit_logs DEFAULT VALUES"))
        assert connection.scalar(text("SELECT id FROM audit_logs")) == 1
    engine.dispose()
