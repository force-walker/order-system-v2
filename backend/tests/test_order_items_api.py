from datetime import UTC, date, datetime
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.entities import Customer, Order, OrderItem, OrderStatus, PricingBasis, Product


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


def _seed_customer_and_product() -> tuple[int, int]:
    db = TestingSessionLocal()
    suffix = uuid4().hex[:8]
    customer = Customer(customer_code=f"C-ATOMIC-{suffix}", name="Atomic Customer", active=True)
    product = Product(
        sku=f"SKU-ATOMIC-{suffix}",
        name="Atomic Product",
        order_uom="count",
        purchase_uom="count",
        invoice_uom="count",
        is_catch_weight=False,
        weight_capture_required=False,
        pricing_basis_default=PricingBasis.uom_count,
        active=True,
    )
    db.add_all([customer, product])
    db.commit()
    result = (customer.id, product.id)
    db.close()
    return result


def _atomic_order_payload(customer_id: int, product_id: int) -> dict:
    return {
        "customer_id": customer_id,
        "delivery_date": str(date.today()),
        "items": [
            {
                "product_id": product_id,
                "ordered_qty": 2,
                "order_uom_type": "uom_count",
                "pricing_basis": "uom_count",
                "unit_price_uom_count": 100,
            }
        ],
    }


def test_create_order_with_items_is_atomic_and_requires_at_least_one_item():
    customer_id, product_id = _seed_customer_and_product()
    client = _client()

    with TestingSessionLocal() as db:
        initial_orders = db.query(Order).count()

    empty = client.post(
        "/api/v1/orders/with-items",
        json={"customer_id": customer_id, "delivery_date": str(date.today()), "items": []},
    )
    assert empty.status_code == 422

    missing_product_payload = _atomic_order_payload(customer_id, 999999)
    missing_product = client.post("/api/v1/orders/with-items", json=missing_product_payload)
    assert missing_product.status_code == 404
    assert missing_product.json()["detail"]["code"] == "PRODUCT_NOT_FOUND"

    with TestingSessionLocal() as db:
        assert db.query(Order).count() == initial_orders

    created = client.post(
        "/api/v1/orders/with-items",
        json=_atomic_order_payload(customer_id, product_id),
    )
    assert created.status_code == 201
    assert created.json()["order"]["customer_id"] == customer_id
    assert len(created.json()["items"]) == 1
    assert created.json()["items"][0]["order_id"] == created.json()["order"]["id"]

    with TestingSessionLocal() as db:
        assert db.query(Order).count() == initial_orders + 1
        assert db.query(OrderItem).filter(OrderItem.order_id == created.json()["order"]["id"]).count() == 1


def test_order_line_reference_uses_permanent_document_sequence_not_date_tracking():
    customer_id, product_id = _seed_customer_and_product()
    db = TestingSessionLocal()
    suffix = uuid4().hex[:8]
    orders = [
        Order(
            order_no=f"ORD-20000101-54321-{suffix}",
            tracking_no="20000101-54321",
            customer_id=customer_id,
            order_datetime=datetime.now(UTC),
            delivery_date=date.today(),
            status=OrderStatus.new,
            created_by="system_api",
            updated_by="system_api",
        ),
        Order(
            order_no=f"ORD-20000102-54321-{suffix}",
            tracking_no="20000102-54321",
            customer_id=customer_id,
            order_datetime=datetime.now(UTC),
            delivery_date=date.today(),
            status=OrderStatus.new,
            created_by="system_api",
            updated_by="system_api",
        ),
    ]
    db.add_all(orders)
    db.commit()
    order_ids = [order.id for order in orders]
    db.close()

    client = _client()
    payload = _atomic_order_payload(customer_id, product_id)["items"][0]
    first = client.post(f"/api/v1/orders/{order_ids[0]}/items", json=payload)
    second = client.post(f"/api/v1/orders/{order_ids[1]}/items", json=payload)
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["line_no"] == 10
    assert second.json()["line_no"] == 10
    assert first.json()["line_ref"].endswith("-0010")
    assert second.json()["line_ref"].endswith("-0010")
    assert first.json()["line_ref"] != second.json()["line_ref"]
    assert first.json()["order_line_no"] == first.json()["line_ref"]
    assert second.json()["order_line_no"] == second.json()["line_ref"]


def test_order_items_crud_and_bulk():
    order_id, product_id = _seed_order_and_product()
    client = _client()

    created = client.post(
        f"/api/v1/orders/{order_id}/items",
        json={
            "product_id": product_id,
            "ordered_qty": 2,
            "order_uom_type": "uom_count",
            "estimated_weight_kg": 2.2,
            "target_price": 88,
            "price_ceiling": 120,
            "stockout_policy": "backorder",
            "pricing_basis": "uom_count",
            "unit_price_uom_count": 100,
            "note": "line-1",
            "comment": "line comment",
        },
    )
    assert created.status_code == 201
    item_id = created.json()["id"]
    assert created.json()["uuid"]
    assert created.json()["note"] == "line-1"
    assert created.json()["comment"] == "line comment"
    assert created.json()["order_line_no"].startswith("ODL-")
    assert float(created.json()["estimated_weight_kg"]) == 2.2
    assert float(created.json()["target_price"]) == 88.0
    assert float(created.json()["price_ceiling"]) == 120.0
    assert created.json()["stockout_policy"] == "backorder"

    listed = client.get(f"/api/v1/orders/{order_id}/items")
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["uuid"] == created.json()["uuid"]
    assert listed.json()[0]["order_line_no"] == created.json()["order_line_no"]

    order_uuid = client.get(f"/api/v1/orders/{order_id}").json()["uuid"]
    listed_by_uuid = client.get(f"/api/v1/orders/uuid/{order_uuid}/items")
    assert listed_by_uuid.status_code == 200
    assert listed_by_uuid.json()[0]["id"] == item_id

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

    updated_by_uuid = client.patch(
        f"/api/v1/orders/uuid/{order_uuid}/items/{created.json()['uuid']}",
        json={"ordered_qty": 4},
    )
    assert updated_by_uuid.status_code == 200
    assert float(updated_by_uuid.json()["ordered_qty"]) == 4.0

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
