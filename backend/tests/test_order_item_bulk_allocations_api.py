import re
from datetime import UTC, date, datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.entities import Customer, LineStatus, Order, OrderItem, OrderStatus, PricingBasis, Product, Supplier, SupplierProduct


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


def _seed_order_item(product_name: str = "P", customer_name: str = "C") -> tuple[int, int, int, int]:
    db = TestingSessionLocal()
    supplier = Supplier(supplier_code=f"SUP-{datetime.now(UTC).timestamp()}", name="S", active=True)
    db.add(supplier)
    db.flush()

    customer = Customer(customer_code=f"C-{datetime.now(UTC).timestamp()}", name=customer_name, active=True)
    db.add(customer)
    db.flush()

    product = Product(
        sku=f"SKU-{datetime.now(UTC).timestamp()}",
        name=product_name,
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

    row = [x for x in worklist.json() if x["order_item_id"] == order_item_id][0]
    assert "allocated_supplier_id" in row
    assert "allocated_qty" in row
    assert "delivery_date" in row
    assert re.match(r"^\d{4}-\d{2}-\d{2}$", row["delivery_date"]) is not None

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

    db = TestingSessionLocal()
    item = db.query(OrderItem).filter(OrderItem.id == order_item_id).first()
    order = db.query(Order).filter(Order.id == item.order_id).first()
    assert item is not None and order is not None
    assert item.shipped_date == order.delivery_date
    assert item.line_status == LineStatus.allocated
    db.close()


def test_bulk_save_partial_success_and_validation_conflict():
    ok_item_id, supplier_id, _, _ = _seed_order_item(product_name="OK")
    ng_item_id, _, _, _ = _seed_order_item(product_name="NG")
    client = _client()

    result = client.post(
        "/api/v1/order-item-allocations/bulk-save",
        json={
            "items": [
                {"order_item_id": ok_item_id, "supplier_id": supplier_id, "allocated_qty": 2},
                {"order_item_id": ng_item_id, "supplier_id": supplier_id, "allocated_qty": 999},
            ]
        },
    )
    assert result.status_code == 200
    assert result.json()["succeeded"] == 1
    assert result.json()["failed"] == 1
    assert result.json()["errors"][0]["code"] in {"ALLOCATED_QTY_EXCEEDS_ORDERED_QTY", "SUPPLIER_NOT_FOUND"}

    db = TestingSessionLocal()
    ok_item = db.query(OrderItem).filter(OrderItem.id == ok_item_id).first()
    ng_item = db.query(OrderItem).filter(OrderItem.id == ng_item_id).first()
    assert ok_item is not None and ng_item is not None
    assert ok_item.line_status == LineStatus.allocated
    assert ok_item.shipped_date is not None
    assert ng_item.line_status != LineStatus.allocated
    assert ng_item.shipped_date is None
    db.close()

    bad = client.post(
        "/api/v1/order-item-allocations/bulk-save",
        json={"items": [{"order_item_id": ok_item_id, "supplier_id": supplier_id, "allocated_qty": 0}]},
    )
    assert bad.status_code == 422

    missing_qty = client.post(
        "/api/v1/order-item-allocations/bulk-save",
        json={"items": [{"order_item_id": ok_item_id, "supplier_id": supplier_id}]},
    )
    assert missing_qty.status_code == 200
    assert missing_qty.json()["failed"] == 1
    assert missing_qty.json()["errors"][0]["code"] == "ALLOCATED_QTY_REQUIRED"


def test_bulk_save_can_unassign_supplier_with_null_values():
    order_item_id, supplier_id, _, _ = _seed_order_item()
    client = _client()

    assigned = client.post(
        "/api/v1/order-item-allocations/bulk-save",
        json={"items": [{"order_item_id": order_item_id, "supplier_id": supplier_id, "allocated_qty": 3}]},
    )
    assert assigned.status_code == 200
    assert assigned.json()["succeeded"] == 1

    unassigned = client.post(
        "/api/v1/order-item-allocations/bulk-save",
        json={"items": [{"order_item_id": order_item_id, "supplier_id": None, "allocated_qty": None}]},
    )
    assert unassigned.status_code == 200
    assert unassigned.json()["succeeded"] == 1

    worklist = client.get("/api/v1/order-item-allocations")
    assert worklist.status_code == 200
    row = [x for x in worklist.json() if x["order_item_id"] == order_item_id][0]
    assert row["allocated_supplier_id"] is None
    assert row["allocated_qty"] is None

    bad_unassign = client.post(
        "/api/v1/order-item-allocations/bulk-save",
        json={"items": [{"order_item_id": order_item_id, "supplier_id": None, "allocated_qty": 1}]},
    )
    assert bad_unassign.status_code == 200
    assert bad_unassign.json()["failed"] == 1
    assert bad_unassign.json()["errors"][0]["code"] == "UNASSIGN_WITH_QTY_NOT_ALLOWED"


def test_worklist_filters_by_product_and_customer_with_paging():
    _seed_order_item(product_name="Apple", customer_name="Alpha")
    _seed_order_item(product_name="Banana", customer_name="Beta")
    client = _client()

    by_product = client.get("/api/v1/order-item-allocations?product_name=Apple")
    assert by_product.status_code == 200
    assert len(by_product.json()) >= 1
    assert all("Apple" in row["product_name"] for row in by_product.json())

    by_customer = client.get("/api/v1/order-item-allocations?customer_name=Beta")
    assert by_customer.status_code == 200
    assert len(by_customer.json()) >= 1

    by_none = client.get("/api/v1/order-item-allocations?product_name=Orange")
    assert by_none.status_code == 200
    assert by_none.json() == []

    all_rows = client.get("/api/v1/order-item-allocations")
    assert all_rows.status_code == 200
    assert len(all_rows.json()) >= 2

    paged = client.get("/api/v1/order-item-allocations?limit=1&offset=1")
    assert paged.status_code == 200
    assert len(paged.json()) == 1
