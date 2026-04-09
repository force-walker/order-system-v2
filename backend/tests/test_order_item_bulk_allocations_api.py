from datetime import UTC, date, datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.entities import Customer, Order, OrderItem, OrderStatus, PricingBasis, Product, Supplier, SupplierProduct


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


def _seed_order_item() -> tuple[int, int, int, int]:
    db = TestingSessionLocal()
    supplier = Supplier(supplier_code=f"SUP-{datetime.now(UTC).timestamp()}", name="S", active=True)
    db.add(supplier)
    db.flush()

    customer = Customer(customer_code=f"C-{datetime.now(UTC).timestamp()}", name="C", active=True)
    db.add(customer)
    db.flush()

    product = Product(
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
    db.add(product)
    db.flush()

    order = Order(
        order_no=f"ORD-{datetime.now(UTC).timestamp()}",
        customer_id=customer.id,
        order_datetime=datetime.now(UTC),
        delivery_date=date.today(),
        status=OrderStatus.confirmed,
        note=None,
    )
    db.add(order)
    db.flush()

    item = OrderItem(
        order_id=order.id,
        product_id=product.id,
        ordered_qty=5,
        pricing_basis=PricingBasis.uom_count,
        unit_price_uom_count=100,
        unit_price_uom_kg=None,
    )
    db.add(item)
    db.flush()

    mapping = SupplierProduct(
        supplier_id=supplier.id,
        product_id=product.id,
        priority=1,
        is_preferred=True,
    )
    db.add(mapping)
    db.commit()
    return item.id, supplier.id, product.id, order.id


def test_worklist_suggest_and_bulk_save_flow():
    order_item_id, supplier_id, _, _ = _seed_order_item()
    client = _client()

    worklist = client.get("/api/v1/order-item-allocations?unallocated_only=true")
    assert worklist.status_code == 200
    assert any(x["order_item_id"] == order_item_id for x in worklist.json())

    suggest = client.post("/api/v1/order-item-allocations/suggestions", json={"order_item_ids": [order_item_id]})
    assert suggest.status_code == 200
    assert suggest.json()[0]["suggested_supplier_id"] == supplier_id
    assert "mapping" in suggest.json()[0]["reason"]

    saved = client.post(
        "/api/v1/order-item-allocations/bulk-save",
        json={"items": [{"order_item_id": order_item_id, "supplier_id": supplier_id, "allocated_qty": 3}]},
    )
    assert saved.status_code == 200
    assert saved.json()["succeeded"] == 1
    assert saved.json()["failed"] == 0


def test_bulk_save_partial_success_and_validation_conflict():
    order_item_id, supplier_id, _, _ = _seed_order_item()
    client = _client()

    result = client.post(
        "/api/v1/order-item-allocations/bulk-save",
        json={
            "items": [
                {"order_item_id": order_item_id, "supplier_id": supplier_id, "allocated_qty": 2},
                {"order_item_id": order_item_id, "supplier_id": supplier_id, "allocated_qty": 999},
            ]
        },
    )
    assert result.status_code == 200
    assert result.json()["succeeded"] == 1
    assert result.json()["failed"] == 1
    assert result.json()["errors"][0]["code"] == "ALLOCATED_QTY_EXCEEDS_ORDERED_QTY"

    bad = client.post(
        "/api/v1/order-item-allocations/bulk-save",
        json={"items": [{"order_item_id": order_item_id, "supplier_id": supplier_id, "allocated_qty": 0}]},
    )
    assert bad.status_code == 422
