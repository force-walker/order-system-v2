from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.entities import PricingBasis, Product


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


def _seed_product(sku: str = "SKU-001") -> int:
    db = TestingSessionLocal()
    p = Product(
        sku=sku,
        name="Test Product",
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
    db.add(p)
    db.commit()
    db.refresh(p)
    pid = p.id
    db.close()
    return pid


def test_list_products():
    _seed_product()
    client = _client()
    res = client.get("/api/v1/products")
    assert res.status_code == 200
    body = res.json()
    assert isinstance(body, list)
    assert len(body) >= 1
    assert body[0]["sku"] == "SKU-001"


def test_get_product_not_found():
    client = _client()
    res = client.get("/api/v1/products/999999")
    assert res.status_code == 404
    assert res.json()["detail"]["code"] == "PRODUCT_NOT_FOUND"


def test_get_product_by_id():
    pid = _seed_product("SKU-002")
    client = _client()
    res = client.get(f"/api/v1/products/{pid}")
    assert res.status_code == 200
    assert res.json()["id"] == pid


def test_create_product_success_and_duplicate_conflict():
    client = _client()
    payload = {
        "sku": "SKU-NEW-1",
        "name": "Created Product",
        "order_uom": "count",
        "purchase_uom": "count",
        "invoice_uom": "count",
        "is_catch_weight": False,
        "weight_capture_required": False,
        "pricing_basis_default": "uom_count",
    }
    created = client.post("/api/v1/products", json=payload)
    assert created.status_code == 201
    assert created.json()["sku"] == "SKU-NEW-1"

    dup = client.post("/api/v1/products", json=payload)
    assert dup.status_code == 409
    assert dup.json()["detail"]["code"] == "SKU_ALREADY_EXISTS"


def test_update_product_success_and_not_found():
    pid = _seed_product("SKU-UPD")
    client = _client()

    ok = client.patch(f"/api/v1/products/{pid}", json={"name": "Updated Name", "active": False})
    assert ok.status_code == 200
    assert ok.json()["name"] == "Updated Name"
    assert ok.json()["active"] is False

    nf = client.patch("/api/v1/products/999999", json={"name": "x"})
    assert nf.status_code == 404
    assert nf.json()["detail"]["code"] == "PRODUCT_NOT_FOUND"
