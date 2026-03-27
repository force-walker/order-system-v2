from datetime import UTC, date, datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.auth import issue_tokens
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.entities import (
    BatchJob,
    BatchJobStatus,
    Customer,
    LineStatus,
    Order,
    OrderItem,
    OrderStatus,
    PricingBasis,
    Product,
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


def _auth() -> dict[str, str]:
    access, _, _ = issue_tokens("tester", "admin")
    return {"Authorization": f"Bearer {access}"}


def _seed_product_customer_order() -> tuple[int, int]:
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

    line = OrderItem(
        order_id=o.id,
        product_id=p.id,
        ordered_qty=1,
        pricing_basis=PricingBasis.uom_count,
        unit_price_uom_count=10,
        unit_price_uom_kg=None,
        line_status=LineStatus.open,
    )
    db.add(line)
    db.commit()
    return c.id, o.id


def test_422_for_input_validation_errors():
    client = _client()

    # required field missing
    product_missing = client.post("/api/v1/products", json={"sku": "SKU-X"})
    assert product_missing.status_code == 422

    # enum invalid
    product_enum = client.post(
        "/api/v1/products",
        json={
            "sku": "SKU-Y",
            "name": "P",
            "order_uom": "count",
            "purchase_uom": "count",
            "invoice_uom": "count",
            "pricing_basis_default": "bad_enum",
        },
    )
    assert product_enum.status_code == 422

    # business validation (date range)
    _, order_id = _seed_product_customer_order()
    inv_bad_date = client.post(
        "/api/v1/invoices",
        json={
            "invoice_no": "INV-BAD",
            "order_id": order_id,
            "invoice_date": "2026-03-27",
            "due_date": "2026-03-26",
        },
    )
    assert inv_bad_date.status_code == 422
    assert inv_bad_date.json()["detail"]["code"] == "INVALID_DATE_RANGE"

    # invalid transition pair
    bad_pair = client.post(
        f"/api/v1/orders/{order_id}/bulk-transition",
        json={"from_status": "confirmed", "to_status": "invoiced"},
    )
    assert bad_pair.status_code == 422
    assert bad_pair.json()["detail"]["code"] == "INVALID_TRANSITION_PAIR"


def test_409_for_state_conflicts():
    client = _client()

    # duplicate key conflict
    prod = {
        "sku": "SKU-CONFLICT",
        "name": "P",
        "order_uom": "count",
        "purchase_uom": "count",
        "invoice_uom": "count",
        "pricing_basis_default": "uom_count",
    }
    assert client.post("/api/v1/products", json=prod).status_code == 201
    dup = client.post("/api/v1/products", json=prod)
    assert dup.status_code == 409

    # state mismatch conflict
    _, order_id = _seed_product_customer_order()
    mismatch = client.post(
        f"/api/v1/orders/{order_id}/bulk-transition",
        json={"from_status": "allocated", "to_status": "purchased"},
    )
    assert mismatch.status_code == 409
    assert mismatch.json()["detail"]["code"] == "ORDER_STATUS_MISMATCH"

    # lock/state conflict
    inv = client.post(
        "/api/v1/invoices",
        json={"invoice_no": "INV-CF", "order_id": order_id, "invoice_date": str(date.today())},
    )
    invoice_id = inv.json()["id"]
    assert client.post(f"/api/v1/invoices/{invoice_id}/finalize").status_code == 200
    fin_again = client.post(f"/api/v1/invoices/{invoice_id}/finalize")
    assert fin_again.status_code == 409

    # concurrent/running job conflict
    db = TestingSessionLocal()
    running = BatchJob(
        job_type="allocation_run",
        business_date=date.today(),
        idempotency_key="idem-running-1",
        trace_id="t1",
        request_id="r1",
        actor="tester",
        status=BatchJobStatus.running,
        max_retries=1,
        retry_count=0,
        requested_count=1,
        processed_count=0,
        succeeded_count=0,
        failed_count=0,
        skipped_count=0,
        errors_json="[]",
    )
    db.add(running)
    db.commit()
    db.close()

    batch_conflict = client.post(
        "/api/v1/allocations/runs",
        json={
            "business_date": str(date.today()),
            "idempotency_key": "idem-new-2",
            "requested_count": 1,
        },
        headers=_auth(),
    )
    assert batch_conflict.status_code == 409
    assert batch_conflict.json()["detail"]["code"] == "JOB_ALREADY_RUNNING"
