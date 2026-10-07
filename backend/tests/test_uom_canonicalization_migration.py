import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def _migration():
    path = Path(__file__).parents[1] / "alembic" / "versions" / "2026100602_canonicalize_uom_values.py"
    spec = importlib.util.spec_from_file_location("migration_2026100602", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _schema(connection):
    columns_by_table = {}
    for table, column, nullable in _migration().UOM_COLUMNS:
        columns_by_table.setdefault(table, []).append((column, nullable))
    for table, columns in columns_by_table.items():
        definitions = ", ".join(
            f"{column} VARCHAR(32) {'NULL' if nullable else 'NOT NULL'}"
            for column, nullable in columns
        )
        connection.execute(sa.text(
            f"CREATE TABLE {table} (id INTEGER PRIMARY KEY, {definitions})"
        ))


def test_upgrade_canonicalizes_every_persisted_uom_column(monkeypatch):
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")
    aliases = ["PC", "count", "PIECE", "CTN", "Case", "KG", "Kg"]
    expected = ["piece", "piece", "piece", "case", "case", "kg", "kg"]
    with engine.begin() as connection:
        _schema(connection)
        migration = _migration()
        values_by_table = {}
        for (table, column, _nullable), raw in zip(migration.UOM_COLUMNS, aliases, strict=True):
            values_by_table.setdefault(table, {})[column] = raw
        for table, values in values_by_table.items():
            columns = ", ".join(values)
            binds = ", ".join(f":{column}" for column in values)
            connection.execute(sa.text(f"INSERT INTO {table} (id, {columns}) VALUES (1, {binds})"), values)
        connection.execute(sa.text("INSERT INTO supplier_allocations (id, final_uom) VALUES (2, NULL)"))
        operations = Operations(MigrationContext.configure(connection))
        monkeypatch.setattr(migration, "op", operations)
        migration.upgrade()
        actual = [
            connection.execute(sa.text(f"SELECT {column} FROM {table} WHERE id = 1")).scalar_one()
            for table, column, _nullable in migration.UOM_COLUMNS
        ]
        assert actual == expected
        nullable_table, nullable_column, _ = migration.UOM_COLUMNS[3]
        assert connection.execute(sa.text(
            f"SELECT {nullable_column} FROM {nullable_table} WHERE id = 2"
        )).scalar_one_or_none() is None


def test_upgrade_rejects_unknown_uom_without_rewriting(monkeypatch):
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        _schema(connection)
        migration = _migration()
        values_by_table = {}
        for table, column, nullable in migration.UOM_COLUMNS:
            values_by_table.setdefault(table, {})[column] = None if nullable else "piece"
        for table, values in values_by_table.items():
            columns = ", ".join(values)
            binds = ", ".join(f":{column}" for column in values)
            connection.execute(sa.text(f"INSERT INTO {table} (id, {columns}) VALUES (1, {binds})"), values)
        connection.execute(sa.text("UPDATE products SET order_uom = 'box' WHERE id = 1"))
        operations = Operations(MigrationContext.configure(connection))
        monkeypatch.setattr(migration, "op", operations)
        with pytest.raises(RuntimeError, match="unknown UOM values in products.order_uom"):
            migration.upgrade()
        assert connection.execute(sa.text("SELECT order_uom FROM products WHERE id = 1")).scalar_one() == "box"
