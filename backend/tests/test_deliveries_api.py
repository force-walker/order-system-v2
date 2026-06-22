from datetime import UTC, date, datetime
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.entities import Customer, Delivery, DeliveryItem, LineStatus, Order, OrderItem, OrderStatus, PricingBasis, Product


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


def _seed_purchased_order() -> str:
    db = TestingSessionLocal()
    suffix = uuid4().hex[:8]
    customer = Customer(
        customer_code=f"CUST-DEL-{suffix}",
        name="Delivery Customer",
        active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db.add(customer)
    db.flush()

    product = Product(
        sku=f"SKU-DEL-{suffix}",
        name="Delivery Product",
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
        order_no="pending-seed",
        customer_id=customer.id,
        order_datetime=datetime.now(UTC),
        delivery_date=date.today(),
        status=OrderStatus.purchased,
        note=None,
        created_by="system_api",
        updated_by="system_api",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db.add(order)
    db.flush()

    db.add(
        OrderItem(
            order_id=order.id,
            product_id=product.id,
            ordered_qty=2,
            order_uom_type=PricingBasis.uom_count,
            pricing_basis=PricingBasis.uom_count,
            unit_price_uom_count=100,
            unit_price_uom_kg=None,
            line_status=LineStatus.purchased,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
    )
    db.commit()
    order_id = order.id
    db.close()
    return order_id


def test_ship_transition_creates_delivery_and_items():
    order_id = _seed_purchased_order()
    client = _client()

    shipped = client.post(
        f"/api/v1/orders/{order_id}/bulk-transition",
        json={"from_status": "purchased", "to_status": "shipped"},
    )
    assert shipped.status_code == 200

    listed = client.get(f"/api/v1/deliveries?order_id={order_id}")
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    delivery_id = listed.json()[0]["id"]
    assert listed.json()[0]["delivery_no"].startswith("DLV-")

    items = client.get(f"/api/v1/deliveries/{delivery_id}/items")
    assert items.status_code == 200
    assert len(items.json()) == 1
    assert items.json()[0]["delivery_line_no"].startswith("DLI-")

    db = TestingSessionLocal()
    delivery = db.query(Delivery).filter(Delivery.id == delivery_id).first()
    delivery_item = db.query(DeliveryItem).filter(DeliveryItem.delivery_id == delivery_id).first()
    db.close()
    assert delivery is not None
    assert delivery_item is not None


def test_build_delivery_from_order_and_pdf():
    order_id = _seed_purchased_order()
    client = _client()

    shipped = client.post(
        f"/api/v1/orders/{order_id}/bulk-transition",
        json={"from_status": "purchased", "to_status": "shipped"},
    )
    assert shipped.status_code == 200

    built = client.post("/api/v1/deliveries/from-order", json={"order_id": order_id})
    assert built.status_code == 200
    delivery_id = built.json()["id"]
    assert built.json()["delivery_no"].startswith("DLV-")

    refreshed = client.post(f"/api/v1/deliveries/{delivery_id}/refresh")
    assert refreshed.status_code == 200
    assert refreshed.json()["id"] == delivery_id

    pdf = client.get(f"/api/v1/deliveries/{delivery_id}/pdf")
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert len(pdf.content) > 0


def test_list_delivery_invoices():
    order_id = _seed_purchased_order()
    client = _client()

    shipped = client.post(
        f"/api/v1/orders/{order_id}/bulk-transition",
        json={"from_status": "purchased", "to_status": "shipped"},
    )
    assert shipped.status_code == 200

    built = client.post("/api/v1/deliveries/from-order", json={"order_id": order_id})
    assert built.status_code == 200
    delivery_id = built.json()["id"]
    delivery_uuid = built.json()["uuid"]

    invoice = client.post(
        "/api/v1/invoices/generate-from-delivery",
        json={"delivery_id": delivery_id, "invoice_date": str(date.today())},
    )
    assert invoice.status_code == 201

    listed = client.get(f"/api/v1/deliveries/{delivery_id}/invoices")
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["invoice_id"] == invoice.json()["id"]
    assert listed.json()[0]["delivery_id"] == delivery_id
    assert listed.json()[0]["delivery_uuid"] == delivery_uuid
    assert listed.json()[0]["delivery_no"].startswith("DLV-")

    listed_by_uuid = client.get(f"/api/v1/deliveries/uuid/{delivery_uuid}/invoices")
    assert listed_by_uuid.status_code == 200
    assert listed_by_uuid.json()[0]["invoice_id"] == invoice.json()["id"]
