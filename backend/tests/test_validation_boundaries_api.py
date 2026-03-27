from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.entities import Customer, LineStatus, Order, OrderItem, OrderStatus, PricingBasis, Product, SupplierAllocation


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


def _seed_order_and_allocation() -> tuple[int, int]:
    db = TestingSessionLocal()

    c = Customer(customer_code=f"C-{datetime.now(UTC).timestamp()}", name="C", active=True)
    db.add(c)
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
    db.flush()

    o = Order(
        order_no=f"ORD-{datetime.now(UTC).timestamp()}",
        customer_id=c.id,
        order_datetime=datetime.now(UTC),
        delivery_date=date.today(),
        status=OrderStatus.confirmed,
        note=None,
    )
    db.add(o)
    db.flush()

    item = OrderItem(
        order_id=o.id,
        product_id=p.id,
        ordered_qty=2,
        pricing_basis=PricingBasis.uom_count,
        unit_price_uom_count=10,
        unit_price_uom_kg=None,
        line_status=LineStatus.open,
    )
    db.add(item)
    db.flush()

    alloc = SupplierAllocation(order_item_id=item.id, final_qty=2, final_uom="count")
    db.add(alloc)
    db.commit()

    return o.id, alloc.id


@pytest.mark.parametrize("basis", ["uom_count", "uom_kg"])
def test_product_enum_all_values_acceptance(basis: str):
    client = _client()
    payload = {
        "sku": f"SKU-B-{basis}",
        "name": "Enum Product",
        "order_uom": "count",
        "purchase_uom": "count",
        "invoice_uom": "count",
        "pricing_basis_default": basis,
    }
    res = client.post("/api/v1/products", json=payload)
    assert res.status_code == 201


def test_product_unknown_enum_and_empty_string_and_length():
    client = _client()

    unknown_enum = client.post(
        "/api/v1/products",
        json={
            "sku": "SKU-UNK",
            "name": "P",
            "order_uom": "count",
            "purchase_uom": "count",
            "invoice_uom": "count",
            "pricing_basis_default": "unknown",
        },
    )
    assert unknown_enum.status_code == 422

    empty_name = client.post(
        "/api/v1/products",
        json={
            "sku": "SKU-EMPTY",
            "name": "",
            "order_uom": "count",
            "purchase_uom": "count",
            "invoice_uom": "count",
            "pricing_basis_default": "uom_count",
        },
    )
    assert empty_name.status_code == 422

    too_long_sku = client.post(
        "/api/v1/products",
        json={
            "sku": "S" * 65,
            "name": "P",
            "order_uom": "count",
            "purchase_uom": "count",
            "invoice_uom": "count",
            "pricing_basis_default": "uom_count",
        },
    )
    assert too_long_sku.status_code == 422


def test_negative_zero_and_empty_string_boundaries():
    order_id, allocation_id = _seed_order_and_allocation()
    client = _client()

    order_customer_zero = client.post(
        "/api/v1/orders",
        json={"customer_id": 0, "delivery_date": str(date.today())},
    )
    assert order_customer_zero.status_code == 422

    inv_order_zero = client.post(
        "/api/v1/invoices",
        json={"invoice_no": "INV-0", "order_id": 0, "invoice_date": str(date.today())},
    )
    assert inv_order_zero.status_code == 422

    alloc_qty_zero = client.patch(
        f"/api/v1/allocations/{allocation_id}/override",
        json={"final_supplier_id": 1, "final_qty": 0, "final_uom": "count", "override_reason_code": "manual"},
    )
    assert alloc_qty_zero.status_code == 422

    alloc_uom_empty = client.patch(
        f"/api/v1/allocations/{allocation_id}/override",
        json={"final_supplier_id": 1, "final_qty": 1, "final_uom": "", "override_reason_code": "manual"},
    )
    assert alloc_uom_empty.status_code == 422

    purchase_result_qty_negative = client.post(
        "/api/v1/purchase-results",
        json={
            "allocation_id": allocation_id,
            "purchased_qty": -1,
            "purchased_uom": "count",
            "result_status": "filled",
            "invoiceable_flag": True,
        },
    )
    assert purchase_result_qty_negative.status_code == 422

    purchase_result_status_empty = client.post(
        "/api/v1/purchase-results",
        json={
            "allocation_id": allocation_id,
            "purchased_qty": 1,
            "purchased_uom": "count",
            "result_status": "",
            "invoiceable_flag": True,
        },
    )
    assert purchase_result_status_empty.status_code == 422

    date_relation = client.post(
        "/api/v1/invoices",
        json={
            "invoice_no": "INV-DATE-BAD",
            "order_id": order_id,
            "invoice_date": str(date.today()),
            "due_date": str(date.today().replace(day=max(1, date.today().day - 1))),
        },
    )
    # if month boundary makes same date impossible to decrement, still accepted; fallback checked below
    if date_relation.status_code != 422:
        date_relation = client.post(
            "/api/v1/invoices",
            json={
                "invoice_no": "INV-DATE-BAD-2",
                "order_id": order_id,
                "invoice_date": "2026-03-27",
                "due_date": "2026-03-26",
            },
        )
    assert date_relation.status_code == 422


def test_transition_from_to_boundaries():
    order_id, _ = _seed_order_and_allocation()
    client = _client()

    same_status = client.post(
        f"/api/v1/orders/{order_id}/bulk-transition",
        json={"from_status": "confirmed", "to_status": "confirmed"},
    )
    assert same_status.status_code == 422

    invalid_pair = client.post(
        f"/api/v1/orders/{order_id}/bulk-transition",
        json={"from_status": "confirmed", "to_status": "invoiced"},
    )
    assert invalid_pair.status_code == 422

    unknown_enum = client.post(
        f"/api/v1/orders/{order_id}/bulk-transition",
        json={"from_status": "bad", "to_status": "allocated"},
    )
    assert unknown_enum.status_code == 422

    valid = client.post(
        f"/api/v1/orders/{order_id}/bulk-transition",
        json={"from_status": "confirmed", "to_status": "allocated"},
    )
    assert valid.status_code == 200
