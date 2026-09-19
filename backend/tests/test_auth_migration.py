import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text


def test_auth_migration_preserves_existing_customer_and_has_no_seed_users():
    path = Path(__file__).parents[1] / "alembic/versions/2026091701_add_auth_users_sessions.py"
    spec = importlib.util.spec_from_file_location("auth_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT)"))
        connection.execute(text("INSERT INTO customers VALUES (1, 'Existing')"))
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            assert {"auth_users", "auth_sessions", "customers"} <= set(inspect(connection).get_table_names())
            assert connection.scalar(text("SELECT count(*) FROM auth_users")) == 0
            assert connection.scalar(text("SELECT name FROM customers WHERE id=1")) == "Existing"
            migration.downgrade()
            assert inspect(connection).get_table_names() == ["customers"]
    engine.dispose()
