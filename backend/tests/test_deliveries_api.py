from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.entities import (
    Customer,
    Delivery,
    DeliveryItem,
    InvoiceItem,
    LineStatus,
    Order,
    OrderItem,
    OrderStatus,
    PricingBasis,
    Product,
    PurchaseResult,
    PurchaseResultStatus,
    SupplierAllocation,
    SystemSettings,
)


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


def _seed_purchased_order(
    *,
    quantity: float = 2,
    order_uom: str = "count",
    invoice_uom: str | None = None,
    is_catch_weight: bool = False,
    actual_weight_kg: float | None = None,
) -> str:
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
        order_uom=order_uom,
        purchase_uom=order_uom,
        invoice_uom=invoice_uom or order_uom,
        is_catch_weight=is_catch_weight,
        weight_capture_required=is_catch_weight,
        pricing_basis_default=(PricingBasis.uom_kg if is_catch_weight else PricingBasis.uom_count),
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
            ordered_qty=quantity,
            order_uom_type=(PricingBasis.uom_kg if is_catch_weight else PricingBasis.uom_count),
            pricing_basis=(PricingBasis.uom_kg if is_catch_weight else PricingBasis.uom_count),
            unit_price_uom_count=(None if is_catch_weight else 100),
            unit_price_uom_kg=(100 if is_catch_weight else None),
            actual_weight_kg=actual_weight_kg,
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
    assert listed.json()[0]["delivery_no"].startswith("DEL-")

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


@pytest.mark.parametrize(
    ("quantity", "order_uom", "actual_weight_kg"),
    [(2, "CTN", None), (5, "PC", 21.73)],
)
def test_delivery_always_uses_order_quantity_axis(quantity: float, order_uom: str, actual_weight_kg: float | None):
    order_id = _seed_purchased_order(quantity=quantity, order_uom=order_uom)
    if actual_weight_kg is not None:
        db = TestingSessionLocal()
        item = db.query(OrderItem).filter(OrderItem.order_id == order_id).one()
        allocation = SupplierAllocation(order_item_id=item.id, final_qty=quantity, final_uom=order_uom)
        db.add(allocation)
        db.flush()
        db.add(
            PurchaseResult(
                allocation_id=allocation.id,
                purchased_qty=quantity,
                purchased_uom=order_uom,
                actual_weight_kg=actual_weight_kg,
                result_status=PurchaseResultStatus.filled,
                invoiceable_flag=True,
            )
        )
        db.commit()
        db.close()
    client = _client()
    shipped = client.post(
        f"/api/v1/orders/{order_id}/bulk-transition",
        json={"from_status": "purchased", "to_status": "shipped"},
    )
    assert shipped.status_code == 200
    delivery = client.get(f"/api/v1/deliveries?order_id={order_id}").json()[0]
    items = client.get(f"/api/v1/deliveries/{delivery['id']}/items")
    assert items.status_code == 200
    assert float(items.json()[0]["delivered_qty"]) == quantity
    assert items.json()[0]["delivered_uom"] == order_uom


def test_catch_weight_split_purchase_results_keep_delivery_ctn_and_invoice_kg():
    order_id = _seed_purchased_order(
        quantity=2,
        order_uom="CTN",
        invoice_uom="KG",
        is_catch_weight=True,
        actual_weight_kg=999,
    )
    db = TestingSessionLocal()
    item = db.query(OrderItem).filter(OrderItem.order_id == order_id).one()
    result_ids: list[int] = []
    for weight in (10.42, 11.31):
        allocation = SupplierAllocation(order_item_id=item.id, final_qty=1, final_uom="CTN")
        db.add(allocation)
        db.flush()
        result = PurchaseResult(
            allocation_id=allocation.id,
            purchased_qty=1,
            purchased_uom="CTN",
            actual_weight_kg=weight,
            final_unit_cost=1000,
            result_status=PurchaseResultStatus.filled,
            invoiceable_flag=True,
        )
        db.add(result)
        db.flush()
        result_ids.append(result.id)
    if db.get(SystemSettings, 1) is None:
        db.add(
            SystemSettings(
                id=1,
                exchange_rate=Decimal("1.0000"),
                jp_gross_margin_pct=Decimal("25.000"),
                hk_gross_margin_pct=Decimal("25.000"),
                freight_unit_price=Decimal("0.00"),
            )
        )
    db.commit()
    db.close()

    client = _client()
    shipped = client.post(
        f"/api/v1/orders/{order_id}/bulk-transition",
        json={"from_status": "purchased", "to_status": "shipped"},
    )
    assert shipped.status_code == 200
    delivery = client.get(f"/api/v1/deliveries?order_id={order_id}").json()[0]
    delivery_items = client.get(f"/api/v1/deliveries/{delivery['id']}/items").json()
    assert len(delivery_items) == 1
    assert float(delivery_items[0]["delivered_qty"]) == 2
    assert delivery_items[0]["delivered_uom"] == "CTN"

    draft = client.post(
        "/api/v1/invoices/generate-draft-from-purchase-results",
        json={"order_id": order_id, "invoice_date": str(date.today()), "purchase_result_ids": result_ids},
    )
    assert draft.status_code == 201, draft.text
    db = TestingSessionLocal()
    invoice_item = db.query(InvoiceItem).filter(InvoiceItem.invoice_id == draft.json()["invoice_id"]).one()
    assert float(invoice_item.billable_qty) == 21.73
    assert invoice_item.billable_uom == "KG"
    db.close()


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
    assert built.json()["delivery_no"].startswith("DEL-")

    refreshed = client.post(f"/api/v1/deliveries/{delivery_id}/refresh")
    assert refreshed.status_code == 200
    assert refreshed.json()["id"] == delivery_id

    rebuilt = client.post("/api/v1/deliveries/from-order", json={"order_id": order_id})
    assert rebuilt.status_code == 200
    assert rebuilt.json()["id"] == delivery_id
    db = TestingSessionLocal()
    assert db.query(Delivery).filter(Delivery.order_id == order_id).count() == 1
    assert db.query(DeliveryItem).filter(DeliveryItem.delivery_id == delivery_id).count() == 1
    db.close()

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
    assert listed.json()[0]["delivery_no"].startswith("DEL-")

    listed_by_uuid = client.get(f"/api/v1/deliveries/uuid/{delivery_uuid}/invoices")
    assert listed_by_uuid.status_code == 200
    assert listed_by_uuid.json()[0]["invoice_id"] == invoice.json()["id"]
