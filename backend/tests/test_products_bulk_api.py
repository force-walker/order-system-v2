from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.entities import PricingBasis, Product


engine = create_engine(
    "sqlite+pysqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    future=True,
)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base.metadata.create_all(bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def _client() -> TestClient:
    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def _seed_product(sku: str) -> int:
    db = TestingSessionLocal()
    row = Product(
        sku=sku,
        name="Seed",
        order_uom="count",
        purchase_uom="count",
        invoice_uom="count",
        is_catch_weight=False,
        weight_capture_required=False,
        pricing_basis_default=PricingBasis.uom_count,
        active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    rid = row.id
    db.close()
    return rid


def test_products_bulk_create_with_partial_failure():
    _seed_product("SKU-BULK-EXIST")
    client = _client()

    res = client.post(
        "/api/v1/products/bulk/create",
        json={
            "items": [
                {
                    "sku": "SKU-BULK-EXIST",
                    "name": "Dup",
                    "order_uom": "count",
                    "purchase_uom": "count",
                    "invoice_uom": "count",
                    "pricing_basis_default": "uom_count",
                },
                {
                    "sku": "SKU-BULK-NEW",
                    "name": "New",
                    "order_uom": "count",
                    "purchase_uom": "count",
                    "invoice_uom": "count",
                    "pricing_basis_default": "uom_count",
                },
            ]
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["summary"] == {"total": 2, "success": 1, "failed": 1}
    assert body["errors"][0]["code"] == "SKU_ALREADY_EXISTS"


def test_products_bulk_update_upsert_delete():
    pid = _seed_product("SKU-BULK-U")
    client = _client()

    upd = client.patch(
        "/api/v1/products/bulk/update",
        json={
            "items": [
                {"id": pid, "name": "Updated"},
                {"id": 999999, "name": "Missing"},
            ]
        },
    )
    assert upd.status_code == 200
    assert upd.json()["summary"] == {"total": 2, "success": 1, "failed": 1}

    upsert = client.post(
        "/api/v1/products/bulk/upsert",
        json={
            "items": [
                {
                    "sku": "SKU-BULK-U",
                    "name": "Updated2",
                    "order_uom": "count",
                    "purchase_uom": "count",
                    "invoice_uom": "count",
                    "pricing_basis_default": "uom_count",
                },
                {
                    "sku": "SKU-BULK-NEW2",
                    "name": "Created2",
                    "order_uom": "count",
                    "purchase_uom": "count",
                    "invoice_uom": "count",
                    "pricing_basis_default": "uom_count",
                },
            ]
        },
    )
    assert upsert.status_code == 200
    assert upsert.json()["summary"] == {"total": 2, "success": 2, "failed": 0}

    all_products = client.get("/api/v1/products").json()
    delete_ids = [p["id"] for p in all_products[:2]]
    delete = client.request("DELETE", "/api/v1/products/bulk/delete", json={"ids": delete_ids + [999999]})
    assert delete.status_code == 200
    assert delete.json()["summary"] == {"total": 3, "success": 2, "failed": 1}
