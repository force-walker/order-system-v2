from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.entities import Supplier


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


def _seed_supplier(code: str = "SUP-001") -> int:
    db = TestingSessionLocal()
    row = Supplier(
        supplier_code=code,
        name="Supplier",
        active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    sid = row.id
    db.close()
    return sid


def test_list_suppliers():
    _seed_supplier("SUP-LIST")
    client = _client()

    res = client.get("/api/v1/suppliers")
    assert res.status_code == 200
    assert any(x["supplier_code"] == "SUP-LIST" for x in res.json())


def test_get_supplier_success_and_not_found():
    supplier_id = _seed_supplier("SUP-GET")
    client = _client()

    ok = client.get(f"/api/v1/suppliers/{supplier_id}")
    assert ok.status_code == 200
    assert ok.json()["id"] == supplier_id

    nf = client.get("/api/v1/suppliers/999999")
    assert nf.status_code == 404
    assert nf.json()["detail"]["code"] == "SUPPLIER_NOT_FOUND"


def test_create_supplier_success_and_duplicate_conflict():
    client = _client()
    payload = {"supplier_code": "SUP-NEW", "name": "New Supplier", "active": True}

    created = client.post("/api/v1/suppliers", json=payload)
    assert created.status_code == 201
    assert created.json()["supplier_code"] == "SUP-NEW"

    dup = client.post("/api/v1/suppliers", json=payload)
    assert dup.status_code == 409
    assert dup.json()["detail"]["code"] == "SUPPLIER_CODE_ALREADY_EXISTS"


def test_create_supplier_validation_error_is_422():
    client = _client()

    bad = client.post("/api/v1/suppliers", json={"supplier_code": ""})
    assert bad.status_code == 422


def test_update_supplier_success_and_not_found():
    supplier_id = _seed_supplier("SUP-UPD")
    client = _client()

    ok = client.patch(f"/api/v1/suppliers/{supplier_id}", json={"name": "Updated Supplier", "active": False})
    assert ok.status_code == 200
    assert ok.json()["name"] == "Updated Supplier"
    assert ok.json()["active"] is False

    nf = client.patch("/api/v1/suppliers/999999", json={"name": "x"})
    assert nf.status_code == 404
    assert nf.json()["detail"]["code"] == "SUPPLIER_NOT_FOUND"


def test_update_supplier_validation_error_is_422():
    supplier_id = _seed_supplier("SUP-UPD-422")
    client = _client()

    bad = client.patch(f"/api/v1/suppliers/{supplier_id}", json={"name": ""})
    assert bad.status_code == 422
