from datetime import UTC, date, datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.entities import Customer, Order, OrderStatus, PricingBasis, Product


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


def _seed_order_and_product() -> tuple[int, int]:
    db = TestingSessionLocal()
    c = Customer(customer_code=f"C-{datetime.now(UTC).timestamp()}", name="C", active=True)
    db.add(c)
    db.flush()

    o = Order(
        order_no=f"ORD-{datetime.now(UTC).timestamp()}",
        customer_id=c.id,
        order_datetime=datetime.now(UTC),
        delivery_date=date.today(),
        status=OrderStatus.new,
        created_by="system_api",
        updated_by="system_api",
    )
    db.add(o)
    db.flush()

    p = Product(
        sku=f"SKU-{datetime.now(UTC).timestamp()}",
        name="P",
        order_uom="count",
        purchase_uom="count",
        invoice_uom="count",
        is_catch_weight=False,
        weight_capture_required=False,
        pricing_basis_default=PricingBasis.uom_count,
        active=True,
    )
    db.add(p)
    db.commit()
    return o.id, p.id


def test_order_items_crud_and_bulk():
    order_id, product_id = _seed_order_and_product()
    client = _client()

    created = client.post(
        f"/api/v1/orders/{order_id}/items",
        json={
            "product_id": product_id,
            "ordered_qty": 2,
            "order_uom_type": "uom_count",
            "pricing_basis": "uom_count",
            "unit_price_uom_count": 100,
            "note": "line-1",
        },
    )
    assert created.status_code == 201
    item_id = created.json()["id"]
    assert created.json()["note"] == "line-1"

    listed = client.get(f"/api/v1/orders/{order_id}/items")
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    bulk = client.post(
        f"/api/v1/orders/{order_id}/items/bulk",
        json={
            "items": [
                {
                    "product_id": product_id,
                    "ordered_qty": 1,
                    "order_uom_type": "uom_count",
                    "pricing_basis": "uom_count",
                    "unit_price_uom_count": 50,
                },
                {
                    "product_id": 999999,
                    "ordered_qty": 1,
                    "order_uom_type": "uom_count",
                    "pricing_basis": "uom_count",
                    "unit_price_uom_count": 50,
                },
            ]
        },
    )
    assert bulk.status_code == 200
    assert bulk.json()["total"] == 2
    assert bulk.json()["success"] == 1
    assert bulk.json()["failed"] == 1

    updated = client.patch(
        f"/api/v1/orders/{order_id}/items/{item_id}",
        json={"ordered_qty": 3, "note": "updated"},
    )
    assert updated.status_code == 200
    assert float(updated.json()["ordered_qty"]) == 3.0
    assert updated.json()["note"] == "updated"

    deleted = client.delete(f"/api/v1/orders/{order_id}/items/{item_id}")
    assert deleted.status_code == 204


def test_order_items_pricing_validation_and_not_found():
    order_id, product_id = _seed_order_and_product()
    client = _client()

    bad = client.post(
        f"/api/v1/orders/{order_id}/items",
        json={
            "product_id": product_id,
            "ordered_qty": 2,
            "order_uom_type": "uom_kg",
            "pricing_basis": "uom_kg",
        },
    )
    assert bad.status_code == 422

    nf = client.get("/api/v1/orders/999999/items")
    assert nf.status_code == 404
