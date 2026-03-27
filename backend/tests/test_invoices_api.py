from datetime import UTC, date, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.entities import Customer, Order, OrderStatus


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


def _seed_order() -> int:
    db = TestingSessionLocal()
    c = Customer(customer_code=f"C-I-{datetime.now(UTC).timestamp()}", name="Customer I", active=True)
    db.add(c)
    db.flush()

    o = Order(
        order_no=f"ORD-I-{datetime.now(UTC).timestamp()}",
        customer_id=c.id,
        order_datetime=datetime.now(UTC),
        delivery_date=date.today(),
        status=OrderStatus.confirmed,
        note=None,
    )
    db.add(o)
    db.commit()
    oid = o.id
    db.close()
    return oid


def test_create_invoice_invalid_date_range_is_422():
    order_id = _seed_order()
    client = _client()

    today = date.today()
    bad = client.post(
        "/api/v1/invoices",
        json={
            "invoice_no": "INV-BAD-DATE",
            "order_id": order_id,
            "invoice_date": str(today),
            "due_date": str(today - timedelta(days=1)),
        },
    )
    assert bad.status_code == 422
    assert bad.json()["detail"]["code"] == "INVALID_DATE_RANGE"


def test_create_finalize_unlock_reset_invoice_flow():
    order_id = _seed_order()
    client = _client()

    created = client.post(
        "/api/v1/invoices",
        json={"invoice_no": "INV-001", "order_id": order_id, "invoice_date": str(date.today())},
    )
    assert created.status_code == 201
    invoice_id = created.json()["id"]

    fin = client.post(f"/api/v1/invoices/{invoice_id}/finalize")
    assert fin.status_code == 200
    assert fin.json()["status"] == "finalized"
    assert fin.json()["is_locked"] is True

    unlock = client.post(
        f"/api/v1/invoices/{invoice_id}/unlock",
        json={"unlock_reason_code": "data_fix", "reason_note": "fix"},
    )
    assert unlock.status_code == 200
    assert unlock.json()["is_locked"] is False

    fin2 = client.post(f"/api/v1/invoices/{invoice_id}/finalize")
    assert fin2.status_code == 409

    reset = client.post(
        f"/api/v1/invoices/{invoice_id}/reset-to-draft",
        json={"reset_reason_code": "data_error", "reason_note": "redo"},
    )
    assert reset.status_code == 200
    assert reset.json()["status"] == "draft"
