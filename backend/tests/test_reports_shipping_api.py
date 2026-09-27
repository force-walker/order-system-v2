from datetime import UTC, date, datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.entities import Customer, Delivery, DeliveryItem, Order, OrderItem, OrderStatus, PricingBasis, Product, Supplier, SupplierAllocation


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


def _seed_shipping_row(
    delivery_date: date,
    supplier_name: str,
    customer_name: str,
    product_name: str,
    *,
    order_status: OrderStatus = OrderStatus.allocated,
    with_delivery: bool = True,
    shipped_date: date | None = None,
) -> str:
    db = TestingSessionLocal()

    supplier = Supplier(supplier_code=f"SUP-{supplier_name}-{datetime.now(UTC).timestamp()}", name=supplier_name, active=True)
    db.add(supplier)
    db.flush()

    customer = Customer(customer_code=f"C-{customer_name}-{datetime.now(UTC).timestamp()}", name=customer_name, active=True)
    db.add(customer)
    db.flush()

    product = Product(
        sku=f"SKU-{product_name}-{datetime.now(UTC).timestamp()}",
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
        delivery_date=delivery_date,
        shipped_date=shipped_date or delivery_date,
        status=order_status,
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
        shipped_date=shipped_date or delivery_date,
    )
    db.add(item)
    db.flush()

    db.add(
        SupplierAllocation(
            order_item_id=item.id,
            final_supplier_id=supplier.id,
            final_qty=4,
            final_uom="count",
        )
    )

    if with_delivery:
        delivery = Delivery(
            delivery_no=f"DLV-{delivery_date.strftime('%Y%m%d')}-{str(item.id)[-5:].zfill(5)}-01",
            tracking_no=f"{delivery_date.strftime('%Y%m%d')}-{str(item.id)[-5:].zfill(5)}",
            order_id=order.id,
            customer_id=customer.id,
            delivery_date=delivery_date,
            shipped_date=shipped_date or delivery_date,
        )
        db.add(delivery)
        db.flush()
        db.add(
            DeliveryItem(
                delivery_id=delivery.id,
                order_item_id=item.id,
                product_id=product.id,
                delivery_line_no=f"DLI-{str(item.id)[-5:].zfill(5)}-01-0001",
                delivered_qty=5,
                delivered_uom="count",
                shipped_date=shipped_date or delivery_date,
            )
        )

    db.commit()
    item_id = item.id
    db.close()
    return item_id


def test_shipping_report_same_date_and_sort_modes():
    delivery_date = date(2026, 4, 16)
    _seed_shipping_row(delivery_date, supplier_name="B-Supplier", customer_name="A-Customer", product_name="Apple")
    _seed_shipping_row(delivery_date, supplier_name="A-Supplier", customer_name="C-Customer", product_name="Banana")
    _seed_shipping_row(delivery_date, supplier_name="A-Supplier", customer_name="B-Customer", product_name="Apple")
    client = _client()

    by_supplier = client.get(f"/api/v1/reports/shipping?delivery_date={delivery_date}&mode=supplier_product")
    assert by_supplier.status_code == 200
    assert len(by_supplier.json()) == 3
    assert by_supplier.json()[0]["delivery_no"].startswith("DLV-")
    assert [(row["supplier_name"], row["product_name"]) for row in by_supplier.json()] == [
        ("A-Supplier", "Apple"),
        ("A-Supplier", "Banana"),
        ("B-Supplier", "Apple"),
    ]
    assert all(float(row["quantity"]) == 4 for row in by_supplier.json())
    assert all(row["unit"] == "count" for row in by_supplier.json())

    by_customer = client.get(f"/api/v1/reports/shipping?delivery_date={delivery_date}&mode=customer")
    assert by_customer.status_code == 200
    assert len(by_customer.json()) == 3
    assert by_customer.json()[0]["customer_name"] <= by_customer.json()[1]["customer_name"]


def test_shipping_report_empty_result_is_200_array():
    client = _client()
    res = client.get("/api/v1/reports/shipping?delivery_date=2099-01-01&mode=supplier_product")
    assert res.status_code == 200
    assert res.json() == []


def test_shipping_report_uses_explicit_operational_order_statuses():
    delivery_date = date(2026, 4, 17)
    included = {
        OrderStatus.allocated,
        OrderStatus.purchased,
    }
    excluded = {
        OrderStatus.new,
        OrderStatus.confirmed,
        OrderStatus.shipped,
        OrderStatus.invoiced,
        OrderStatus.cancelled,
    }
    for status in included | excluded:
        _seed_shipping_row(
            delivery_date,
            supplier_name=f"Supplier-{status.value}",
            customer_name=f"Customer-{status.value}",
            product_name=f"Product-{status.value}",
            order_status=status,
        )
    no_delivery_ids = {
        _seed_shipping_row(
            delivery_date,
            supplier_name=f"Supplier-no-delivery-{status.value}",
            customer_name=f"Customer-no-delivery-{status.value}",
            product_name=f"Product-no-delivery-{status.value}",
            order_status=status,
            with_delivery=False,
        )
        for status in included
    }

    response = _client().get(f"/api/v1/reports/shipping?delivery_date={delivery_date}&mode=supplier_product")

    assert response.status_code == 200
    product_names = {row["product_name"] for row in response.json()}
    assert product_names == {
        *(f"Product-{status.value}" for status in included),
        *(f"Product-no-delivery-{status.value}" for status in included),
    }
    no_delivery_rows = [row for row in response.json() if row["order_item_id"] in no_delivery_ids]
    assert len(no_delivery_rows) == 2
    assert all(row["delivery_id"] is None for row in no_delivery_rows)
    assert all(row["delivery_item_id"] is None for row in no_delivery_rows)
    assert all(row["delivery_no"] is None for row in no_delivery_rows)


def test_shipping_report_filters_only_by_order_delivery_date():
    target_date = date(2026, 4, 18)
    different_date = date(2026, 4, 19)
    allocated_id = _seed_shipping_row(
        target_date,
        supplier_name="Supplier-allocated-date",
        customer_name="Customer-allocated-date",
        product_name="Product-allocated-date",
        order_status=OrderStatus.allocated,
        with_delivery=False,
        shipped_date=different_date,
    )
    purchased_id = _seed_shipping_row(
        target_date,
        supplier_name="Supplier-purchased-date",
        customer_name="Customer-purchased-date",
        product_name="Product-purchased-date",
        order_status=OrderStatus.purchased,
        with_delivery=False,
        shipped_date=different_date,
    )
    excluded_id = _seed_shipping_row(
        different_date,
        supplier_name="Supplier-wrong-delivery-date",
        customer_name="Customer-wrong-delivery-date",
        product_name="Product-wrong-delivery-date",
        order_status=OrderStatus.allocated,
        shipped_date=target_date,
    )

    response = _client().get(f"/api/v1/reports/shipping?delivery_date={target_date}&mode=supplier_product")

    assert response.status_code == 200
    rows_by_id = {row["order_item_id"]: row for row in response.json()}
    assert set(rows_by_id) == {allocated_id, purchased_id}
    assert excluded_id not in rows_by_id
    assert all(row["delivery_date"] == target_date.isoformat() for row in rows_by_id.values())
    assert all(row["delivery_id"] is None for row in rows_by_id.values())
