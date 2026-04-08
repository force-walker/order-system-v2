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


def test_create_product_auto_code_and_manual_code_rejected():
    client = _client()
    payload = {
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
    assert created.json()["sku"].startswith("SKU-")

    manual = client.post("/api/v1/products", json={**payload, "sku": "SKU-MANUAL"})
    assert manual.status_code == 422


def test_create_product_validation_errors_are_422():
    client = _client()
    missing_required = client.post("/api/v1/products", json={"name": "X"})
    assert missing_required.status_code == 422

    invalid_enum = client.post(
        "/api/v1/products",
        json={
            "name": "X",
            "order_uom": "count",
            "purchase_uom": "count",
            "invoice_uom": "count",
            "pricing_basis_default": "unknown_basis",
        },
    )
    assert invalid_enum.status_code == 422


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


def test_create_product_auto_code_generation_is_sequential():
    client = _client()
    common = {
        "name": "Auto Product",
        "order_uom": "count",
        "purchase_uom": "count",
        "invoice_uom": "count",
        "pricing_basis_default": "uom_count",
    }

    first = client.post("/api/v1/products", json=common)
    second = client.post("/api/v1/products", json=common)

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["sku"].startswith("SKU-")
    assert second.json()["sku"].startswith("SKU-")

    n1 = int(first.json()["sku"].split("-")[-1])
    n2 = int(second.json()["sku"].split("-")[-1])
    assert n2 == n1 + 1
