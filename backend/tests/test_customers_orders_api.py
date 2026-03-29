from datetime import UTC, date, datetime
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.entities import Customer, LineStatus, Order, OrderItem, OrderStatus, PricingBasis, Product


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


def _seed_customer(code: str = "CUST-001") -> int:
    db = TestingSessionLocal()
    c = Customer(
        customer_code=code,
        name="Test Customer",
        active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    cid = c.id
    db.close()
    return cid


def test_list_customers():
    _seed_customer("CUST-LIST")
    client = _client()
    res = client.get("/api/v1/customers")
    assert res.status_code == 200
    assert isinstance(res.json(), list)
    assert any(x["customer_code"] == "CUST-LIST" for x in res.json())


def test_create_customer_success_and_duplicate_conflict():
    client = _client()
    payload = {"customer_code": "CUST-NEW", "name": "New Customer", "active": True}
    created = client.post("/api/v1/customers", json=payload)
    assert created.status_code == 201
    assert created.json()["customer_code"] == "CUST-NEW"

    dup = client.post("/api/v1/customers", json=payload)
    assert dup.status_code == 409
    assert dup.json()["detail"]["code"] == "CUSTOMER_CODE_ALREADY_EXISTS"


def test_update_customer_success_and_not_found():
    cid = _seed_customer("CUST-UPD")
    client = _client()

    ok = client.patch(f"/api/v1/customers/{cid}", json={"name": "Updated Customer", "active": False})
    assert ok.status_code == 200
    assert ok.json()["name"] == "Updated Customer"
    assert ok.json()["active"] is False

    nf = client.patch("/api/v1/customers/999999", json={"name": "x"})
    assert nf.status_code == 404
    assert nf.json()["detail"]["code"] == "CUSTOMER_NOT_FOUND"


def test_create_customer_validation_error_is_422():
    client = _client()
    res = client.post("/api/v1/customers", json={"customer_code": "CUST-ONLY"})
    assert res.status_code == 422


def test_get_customer_not_found():
    client = _client()
    res = client.get("/api/v1/customers/999999")
    assert res.status_code == 404
    assert res.json()["detail"]["code"] == "CUSTOMER_NOT_FOUND"


def test_create_order_success_and_list():
    cid = _seed_customer("CUST-ORDER")
    payload = {
        "customer_id": cid,
        "delivery_date": str(date.today()),
        "note": "first order",
    }
    client = _client()
    create_res = client.post("/api/v1/orders", json=payload)
    assert create_res.status_code == 201
    assert create_res.json()["order_no"].startswith("ORD-")
    assert create_res.json()["created_by"] == "system_api"
    assert create_res.json()["updated_by"] == "system_api"

    list_res = client.get("/api/v1/orders")
    assert list_res.status_code == 200
    assert any(x["id"] == create_res.json()["id"] for x in list_res.json())

    order_id = create_res.json()["id"]
    detail_res = client.get(f"/api/v1/orders/{order_id}")
    assert detail_res.status_code == 200
    assert detail_res.json()["id"] == order_id


def test_create_order_customer_not_found():
    payload = {
        "customer_id": 999999,
        "delivery_date": str(date.today()),
    }
    client = _client()
    res = client.post("/api/v1/orders", json=payload)
    assert res.status_code == 404
    assert res.json()["detail"]["code"] == "CUSTOMER_NOT_FOUND"


def test_create_order_auto_numbering_generates_unique_order_no():
    cid = _seed_customer("CUST-DUP")
    payload = {
        "customer_id": cid,
        "delivery_date": str(date.today()),
    }
    client = _client()
    first = client.post("/api/v1/orders", json=payload)
    assert first.status_code == 201

    second = client.post("/api/v1/orders", json=payload)
    assert second.status_code == 201
    assert first.json()["order_no"] != second.json()["order_no"]


def test_update_order_header_success_and_not_found():
    cid = _seed_customer("CUST-ORD-UPD")
    cid2 = _seed_customer("CUST-ORD-UPD-2")
    client = _client()

    created = client.post(
        "/api/v1/orders",
        json={"customer_id": cid, "delivery_date": str(date.today()), "note": "before"},
    )
    assert created.status_code == 201
    oid = created.json()["id"]

    ok = client.patch(
        f"/api/v1/orders/{oid}",
        json={"customer_id": cid2, "delivery_date": str(date.today()), "note": "after"},
    )
    assert ok.status_code == 200
    assert ok.json()["customer_id"] == cid2
    assert ok.json()["note"] == "after"

    nf = client.patch("/api/v1/orders/999999", json={"note": "x"})
    assert nf.status_code == 404
    assert nf.json()["detail"]["code"] == "ORDER_NOT_FOUND"


def test_update_order_customer_not_found():
    cid = _seed_customer("CUST-ORD-UPD-NF")
    client = _client()
    created = client.post(
        "/api/v1/orders",
        json={"customer_id": cid, "delivery_date": str(date.today())},
    )
    oid = created.json()["id"]

    bad = client.patch(f"/api/v1/orders/{oid}", json={"customer_id": 999999})
    assert bad.status_code == 404
    assert bad.json()["detail"]["code"] == "CUSTOMER_NOT_FOUND"


def test_get_order_not_found():
    client = _client()
    res = client.get("/api/v1/orders/999999")
    assert res.status_code == 404
    assert res.json()["detail"]["code"] == "ORDER_NOT_FOUND"


def _seed_order_with_open_line() -> int:
    db = TestingSessionLocal()
    suffix = uuid4().hex[:8]

    customer = Customer(
        customer_code=f"CUST-TRANS-{suffix}",
        name="Transition Customer",
        active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db.add(customer)
    db.flush()

    product = Product(
        sku=f"SKU-TRANS-{suffix}",
        name="Transition Product",
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
    db.add(product)
    db.flush()

    order = Order(
        order_no=f"ORD-TRANS-{suffix}",
        customer_id=customer.id,
        order_datetime=datetime.now(UTC),
        delivery_date=date.today(),
        status=OrderStatus.confirmed,
        note=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db.add(order)
    db.flush()

    line = OrderItem(
        order_id=order.id,
        product_id=product.id,
        ordered_qty=2,
        pricing_basis=PricingBasis.uom_count,
        unit_price_uom_count=10,
        unit_price_uom_kg=None,
        line_status=LineStatus.open,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db.add(line)
    db.commit()
    oid = order.id
    db.close()
    return oid


def test_order_bulk_transition_success_and_no_target_lines():
    order_id = _seed_order_with_open_line()
    client = _client()

    ok = client.post(
        f"/api/v1/orders/{order_id}/bulk-transition",
        json={"from_status": "confirmed", "to_status": "allocated"},
    )
    assert ok.status_code == 200
    assert ok.json()["order_id"] == order_id
    assert ok.json()["updated_lines"] == 1
    assert ok.json()["updated_order_status"] == "allocated"

    detail_after = client.get(f"/api/v1/orders/{order_id}")
    assert detail_after.status_code == 200
    assert detail_after.json()["updated_by"] == "system_api"

    no_target = client.post(
        f"/api/v1/orders/{order_id}/bulk-transition",
        json={"from_status": "confirmed", "to_status": "allocated"},
    )
    assert no_target.status_code == 409
    assert no_target.json()["detail"]["code"] == "ORDER_STATUS_MISMATCH"


def test_order_bulk_transition_invalid_pair():
    order_id = _seed_order_with_open_line()
    client = _client()
    bad = client.post(
        f"/api/v1/orders/{order_id}/bulk-transition",
        json={"from_status": "confirmed", "to_status": "invoiced"},
    )
    assert bad.status_code == 422
    assert bad.json()["detail"]["code"] == "INVALID_TRANSITION_PAIR"


def test_order_bulk_transition_same_status_is_422():
    order_id = _seed_order_with_open_line()
    client = _client()
    bad = client.post(
        f"/api/v1/orders/{order_id}/bulk-transition",
        json={"from_status": "confirmed", "to_status": "confirmed"},
    )
    assert bad.status_code == 422
    assert bad.json()["detail"]["code"] == "INVALID_TRANSITION_PAIR"


def test_order_validation_required_and_enum_are_422():
    client = _client()

    missing_required = client.post(
        "/api/v1/orders",
        json={"delivery_date": str(date.today())},
    )
    assert missing_required.status_code == 422

    invalid_enum = client.post(
        "/api/v1/orders/1/bulk-transition",
        json={"from_status": "invalid_status", "to_status": "allocated"},
    )
    assert invalid_enum.status_code == 422
