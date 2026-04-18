from datetime import UTC, date, datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.entities import Customer, Order, OrderItem, OrderStatus, PricingBasis, Product, Supplier, SupplierAllocation


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


def _seed_shipping_row(shipped_date: date, supplier_name: str, customer_name: str, product_name: str) -> None:
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
        delivery_date=shipped_date,
        shipped_date=shipped_date,
        status=OrderStatus.allocated,
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
        shipped_date=shipped_date,
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

    db.commit()
    db.close()


def test_shipping_report_same_date_and_sort_modes():
    sdate = date(2026, 4, 16)
    _seed_shipping_row(sdate, supplier_name="B-Supplier", customer_name="A-Customer", product_name="Banana")
    _seed_shipping_row(sdate, supplier_name="A-Supplier", customer_name="B-Customer", product_name="Apple")
    client = _client()

    by_supplier = client.get(f"/api/v1/reports/shipping?shipped_date={sdate}&mode=supplier_product")
    assert by_supplier.status_code == 200
    assert len(by_supplier.json()) == 2
    assert by_supplier.json()[0]["supplier_name"] <= by_supplier.json()[1]["supplier_name"]

    by_customer = client.get(f"/api/v1/reports/shipping?shipped_date={sdate}&mode=customer")
    assert by_customer.status_code == 200
    assert len(by_customer.json()) == 2
    assert by_customer.json()[0]["customer_name"] <= by_customer.json()[1]["customer_name"]


def test_shipping_report_empty_result_is_200_array():
    client = _client()
    res = client.get("/api/v1/reports/shipping?shipped_date=2099-01-01&mode=supplier_product")
    assert res.status_code == 200
    assert res.json() == []
