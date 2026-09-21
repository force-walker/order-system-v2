"""PostgreSQL regression tests use rollback-only isolated schemas, never public data."""

import importlib.util
import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError


TABLES = ("supplier_allocations", "purchase_results")


def migration():
    path = Path(__file__).parents[1] / "alembic/versions/2026091901_restore_transaction_identities.py"
    spec = importlib.util.spec_from_file_location("transaction_identity_migration", path)
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
        schema = "transaction_identity_repair_test_" + uuid4().hex
        try:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            with Operations.context(MigrationContext.configure(connection)):
                yield connection
        finally:
            transaction.rollback()
    engine.dispose()


def _create_broken_tables(connection, existing: bool) -> None:
    for table_name in TABLES:
        connection.execute(text(f"CREATE TABLE {table_name} (id INTEGER PRIMARY KEY, marker TEXT)"))
        if existing:
            connection.execute(text(f"INSERT INTO {table_name} VALUES (42, 'preserve')"))


@pytest.mark.parametrize("existing", [False, True])
def test_missing_generators_are_repaired_without_losing_rows(pg, existing):
    _create_broken_tables(pg, existing)
    for table_name in TABLES:
        with pytest.raises(IntegrityError):
            with pg.begin_nested():
                pg.execute(text(f"INSERT INTO {table_name} (marker) VALUES ('before')"))

    migration().upgrade()
    expected = 43 if existing else 1
    for table_name in TABLES:
        assert pg.scalar(text(f"INSERT INTO {table_name} (marker) VALUES ('after') RETURNING id")) == expected

    migration().upgrade()  # Must not rewind working generators.
    for table_name in TABLES:
        assert pg.scalar(text(f"INSERT INTO {table_name} (marker) VALUES ('again') RETURNING id")) == expected + 1
        if existing:
            assert pg.scalar(text(f"SELECT marker FROM {table_name} WHERE id=42")) == "preserve"


def test_existing_generators_are_preserved(pg):
    for table_name in TABLES:
        pg.execute(text(f"CREATE TABLE {table_name} (id SERIAL PRIMARY KEY)"))
        pg.execute(text(f"ALTER SEQUENCE {table_name}_id_seq RESTART WITH 99"))
    migration().upgrade()
    for table_name in TABLES:
        assert pg.scalar(text(f"INSERT INTO {table_name} DEFAULT VALUES RETURNING id")) == 99


def test_sqlite_unchanged():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        _create_broken_tables(connection, existing=False)
        with Operations.context(MigrationContext.configure(connection)):
            migration().upgrade()
        for table_name in TABLES:
            connection.execute(text(f"INSERT INTO {table_name} DEFAULT VALUES"))
            assert connection.scalar(text(f"SELECT id FROM {table_name}")) == 1
    engine.dispose()
