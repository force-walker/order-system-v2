import importlib.util
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError


def migration():
    path = Path(__file__).parents[1] / "alembic/versions/2026092001_scope_order_line_number_uniqueness.py"
    spec = importlib.util.spec_from_file_location("order_line_number_scope_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_order_line_number_uniqueness_is_scoped_to_parent_order():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE orders (id TEXT PRIMARY KEY)"))
        connection.execute(
            text(
                "CREATE TABLE order_items ("
                "id TEXT PRIMARY KEY, order_id TEXT NOT NULL, order_line_no TEXT, "
                "FOREIGN KEY(order_id) REFERENCES orders(id))"
            )
        )
        connection.execute(
            text("CREATE UNIQUE INDEX ix_order_items_order_line_no ON order_items (order_line_no)")
        )
        connection.execute(text("INSERT INTO orders (id) VALUES ('order-1'), ('order-2')"))
        connection.execute(
            text(
                "INSERT INTO order_items (id, order_id, order_line_no) "
                "VALUES ('item-1', 'order-1', 'ODL-00001-0001')"
            )
        )

        with Operations.context(MigrationContext.configure(connection)):
            migration().upgrade()

        index = next(
            row for row in inspect(connection).get_indexes("order_items")
            if row["name"] == "ix_order_items_order_line_no"
        )
        assert index["unique"] == 0

        connection.execute(
            text(
                "INSERT INTO order_items (id, order_id, order_line_no) "
                "VALUES ('item-2', 'order-2', 'ODL-00001-0001')"
            )
        )
        with pytest.raises(IntegrityError):
            with connection.begin_nested():
                connection.execute(
                    text(
                        "INSERT INTO order_items (id, order_id, order_line_no) "
                        "VALUES ('item-3', 'order-1', 'ODL-00001-0001')"
                    )
                )
    engine.dispose()
