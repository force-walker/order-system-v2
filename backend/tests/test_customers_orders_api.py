from datetime import date, datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.entities import Customer


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
        code=code,
        name="Test Customer",
        active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
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
    assert any(x["code"] == "CUST-LIST" for x in res.json())


def test_get_customer_not_found():
    client = _client()
    res = client.get("/api/v1/customers/999999")
    assert res.status_code == 404
    assert res.json()["detail"]["code"] == "CUSTOMER_NOT_FOUND"


def test_create_order_success_and_list():
    cid = _seed_customer("CUST-ORDER")
    payload = {
        "order_no": "ORD-001",
        "customer_id": cid,
        "delivery_date": str(date.today()),
        "note": "first order",
    }
    client = _client()
    create_res = client.post("/api/v1/orders", json=payload)
    assert create_res.status_code == 201
    assert create_res.json()["order_no"] == "ORD-001"

    list_res = client.get("/api/v1/orders")
    assert list_res.status_code == 200
    assert any(x["order_no"] == "ORD-001" for x in list_res.json())


def test_create_order_customer_not_found():
    payload = {
        "order_no": "ORD-404",
        "customer_id": 999999,
        "delivery_date": str(date.today()),
    }
    client = _client()
    res = client.post("/api/v1/orders", json=payload)
    assert res.status_code == 404
    assert res.json()["detail"]["code"] == "CUSTOMER_NOT_FOUND"


def test_create_order_duplicate_order_no():
    cid = _seed_customer("CUST-DUP")
    payload = {
        "order_no": "ORD-DUP",
        "customer_id": cid,
        "delivery_date": str(date.today()),
    }
    client = _client()
    first = client.post("/api/v1/orders", json=payload)
    assert first.status_code == 201

    second = client.post("/api/v1/orders", json=payload)
    assert second.status_code == 409
    assert second.json()["detail"]["code"] == "ORDER_NO_ALREADY_EXISTS"
