from datetime import UTC, date, datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.auth import issue_tokens
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.entities import Customer, Order, OrderItem, OrderStatus, PricingBasis, Product, SupplierAllocation


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


def _auth(role: str = "admin") -> dict[str, str]:
    access, _, _ = issue_tokens("regression-user", role)
    return {"Authorization": f"Bearer {access}"}


def _seed_order_with_allocation() -> tuple[int, int, int]:
    db = TestingSessionLocal()
    customer = Customer(code=f"C-R-{datetime.now(UTC).timestamp()}", name="R-C", active=True)
    db.add(customer)
    db.flush()

    product = Product(
        sku=f"SKU-R-{datetime.now(UTC).timestamp()}",
        name="R-P",
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
        order_no=f"ORD-R-{datetime.now(UTC).timestamp()}",
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
        ordered_qty=2,
        pricing_basis=PricingBasis.uom_count,
        unit_price_uom_count=100,
        unit_price_uom_kg=None,
    )
    db.add(item)
    db.flush()

    alloc = SupplierAllocation(order_item_id=item.id, final_supplier_id=1, final_qty=2, final_uom="count")
    db.add(alloc)
    db.commit()

    return customer.id, order.id, alloc.id


def test_products_regression_status_matrix():
    client = _client()

    payload = {
        "sku": "SKU-M-1",
        "name": "P",
        "order_uom": "count",
        "purchase_uom": "count",
        "invoice_uom": "count",
        "pricing_basis_default": "uom_count",
    }

    ok = client.post("/api/v1/products", json=payload)
    assert ok.status_code == 201

    conflict = client.post("/api/v1/products", json=payload)
    assert conflict.status_code == 409

    invalid = client.post(
        "/api/v1/products",
        json={**payload, "sku": "SKU-M-2", "pricing_basis_default": "bad_enum"},
    )
    assert invalid.status_code == 422

    not_found = client.get("/api/v1/products/999999")
    assert not_found.status_code == 404


def test_orders_invoices_and_purchase_results_regression_matrix():
    client = _client()
    customer_id, order_id, allocation_id = _seed_order_with_allocation()

    # orders create 201 / 409 / 422 / 404
    create_order = client.post(
        "/api/v1/orders",
        json={"order_no": "ORD-M-1", "customer_id": customer_id, "delivery_date": str(date.today())},
    )
    assert create_order.status_code == 201

    dup_order = client.post(
        "/api/v1/orders",
        json={"order_no": "ORD-M-1", "customer_id": customer_id, "delivery_date": str(date.today())},
    )
    assert dup_order.status_code == 409

    bad_order = client.post(
        "/api/v1/orders",
        json={"order_no": "ORD-M-2", "customer_id": 0, "delivery_date": str(date.today())},
    )
    assert bad_order.status_code == 422

    nf_order = client.get("/api/v1/orders/999999")
    assert nf_order.status_code == 404

    # transition 200 / 409 / 422 / 404
    transition_ok = client.post(
        f"/api/v1/orders/{order_id}/bulk-transition",
        json={"from_status": "confirmed", "to_status": "allocated"},
    )
    assert transition_ok.status_code == 200

    transition_conflict = client.post(
        f"/api/v1/orders/{order_id}/bulk-transition",
        json={"from_status": "confirmed", "to_status": "allocated"},
    )
    assert transition_conflict.status_code == 409

    transition_invalid = client.post(
        f"/api/v1/orders/{order_id}/bulk-transition",
        json={"from_status": "allocated", "to_status": "allocated"},
    )
    assert transition_invalid.status_code == 422

    transition_nf = client.post(
        "/api/v1/orders/999999/bulk-transition",
        json={"from_status": "confirmed", "to_status": "allocated"},
    )
    assert transition_nf.status_code == 404

    # invoices create/finalize 201/409/422/404
    inv = client.post(
        "/api/v1/invoices",
        json={"invoice_no": "INV-M-1", "order_id": order_id, "invoice_date": str(date.today())},
    )
    assert inv.status_code == 201
    inv_id = inv.json()["id"]

    inv_dup = client.post(
        "/api/v1/invoices",
        json={"invoice_no": "INV-M-1", "order_id": order_id, "invoice_date": str(date.today())},
    )
    assert inv_dup.status_code == 409

    inv_bad = client.post(
        "/api/v1/invoices",
        json={"invoice_no": "INV-M-2", "order_id": order_id, "invoice_date": "2026-03-27", "due_date": "2026-03-26"},
    )
    assert inv_bad.status_code == 422

    fin_ok = client.post(f"/api/v1/invoices/{inv_id}/finalize")
    assert fin_ok.status_code == 200

    fin_conflict = client.post(f"/api/v1/invoices/{inv_id}/finalize")
    assert fin_conflict.status_code == 409

    fin_nf = client.post("/api/v1/invoices/999999/finalize")
    assert fin_nf.status_code == 404

    # purchase-results 201 / 409 / 422 / 404
    pr_ok = client.post(
        "/api/v1/purchase-results",
        json={
            "allocation_id": allocation_id,
            "purchased_qty": 1,
            "purchased_uom": "count",
            "result_status": "filled",
            "invoiceable_flag": True,
        },
    )
    assert pr_ok.status_code == 201

    pr_conflict = client.post(
        "/api/v1/purchase-results",
        json={
            "allocation_id": allocation_id,
            "purchased_qty": 1,
            "purchased_uom": "count",
            "result_status": "filled",
            "invoiceable_flag": True,
        },
    )
    assert pr_conflict.status_code == 409

    pr_bad = client.post(
        "/api/v1/purchase-results",
        json={
            "allocation_id": allocation_id,
            "purchased_qty": 0,
            "purchased_uom": "count",
            "result_status": "filled",
            "invoiceable_flag": True,
        },
    )
    assert pr_bad.status_code == 422

    pr_nf = client.post(
        "/api/v1/purchase-results",
        json={
            "allocation_id": 999999,
            "purchased_qty": 1,
            "purchased_uom": "count",
            "result_status": "filled",
            "invoiceable_flag": True,
        },
    )
    assert pr_nf.status_code == 404


def test_batch_regression_status_matrix():
    client = _client()
    today = str(date.today())

    payload = {
        "business_date": today,
        "idempotency_key": f"idem-reg-{datetime.now(UTC).timestamp()}",
        "requested_count": 2,
    }
    enq = client.post("/api/v1/allocations/runs", json=payload, headers=_auth())
    assert enq.status_code == 202

    # conflict by same date while queued/running with different idempotency key
    conflict = client.post(
        "/api/v1/allocations/runs",
        json={"business_date": today, "idempotency_key": f"idem-reg-2-{datetime.now(UTC).timestamp()}", "requested_count": 1},
        headers=_auth(),
    )
    assert conflict.status_code == 409

    # validation error
    bad = client.post(
        "/api/v1/allocations/runs",
        json={"business_date": today, "idempotency_key": "short", "requested_count": -1},
        headers=_auth(),
    )
    assert bad.status_code == 422

    # not found
    nf = client.get("/api/v1/batch/jobs/999999", headers=_auth())
    assert nf.status_code == 404
