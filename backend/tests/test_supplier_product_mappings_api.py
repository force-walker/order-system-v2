from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.entities import PricingBasis, Product, Supplier


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


def _seed_supplier(code: str = "SUP-MAP-1") -> int:
    db = TestingSessionLocal()
    row = Supplier(supplier_code=code, name="Supplier", active=True, created_at=datetime.now(UTC), updated_at=datetime.now(UTC))
    db.add(row)
    db.commit()
    db.refresh(row)
    sid = row.id
    db.close()
    return sid


def _seed_product(sku: str = "SKU-MAP-1") -> int:
    db = TestingSessionLocal()
    row = Product(
        sku=sku,
        name="Product",
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
    db.add(row)
    db.commit()
    db.refresh(row)
    pid = row.id
    db.close()
    return pid


def test_supplier_product_mapping_crud_and_duplicate_409():
    supplier_id = _seed_supplier("SUP-MAP-A")
    product_id = _seed_product("SKU-MAP-A")
    client = _client()

    created = client.post(
        "/api/v1/supplier-product-mappings",
        json={
            "supplier_id": supplier_id,
            "product_id": product_id,
            "priority": 10,
            "is_preferred": True,
            "default_unit_cost": 99.0,
            "lead_time_days": 2,
            "note": "main",
        },
    )
    assert created.status_code == 201
    mapping_id = created.json()["id"]

    dup = client.post(
        "/api/v1/supplier-product-mappings",
        json={"supplier_id": supplier_id, "product_id": product_id},
    )
    assert dup.status_code == 409
    assert dup.json()["detail"]["code"] == "SUPPLIER_PRODUCT_ALREADY_EXISTS"

    listed = client.get(f"/api/v1/supplier-product-mappings?supplier_id={supplier_id}")
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    updated = client.patch(
        f"/api/v1/supplier-product-mappings/{mapping_id}",
        json={"priority": 5, "default_unit_cost": 88.5, "lead_time_days": 3},
    )
    assert updated.status_code == 200
    assert updated.json()["priority"] == 5

    deleted = client.delete(f"/api/v1/supplier-product-mappings/{mapping_id}")
    assert deleted.status_code == 204


def test_supplier_product_mapping_not_found_and_validation():
    supplier_id = _seed_supplier("SUP-MAP-B")
    product_id = _seed_product("SKU-MAP-B")
    client = _client()

    nf_supplier = client.post(
        "/api/v1/supplier-product-mappings",
        json={"supplier_id": 999999, "product_id": product_id},
    )
    assert nf_supplier.status_code == 404
    assert nf_supplier.json()["detail"]["code"] == "SUPPLIER_NOT_FOUND"

    nf_product = client.post(
        "/api/v1/supplier-product-mappings",
        json={"supplier_id": supplier_id, "product_id": 999999},
    )
    assert nf_product.status_code == 404
    assert nf_product.json()["detail"]["code"] == "PRODUCT_NOT_FOUND"

    nf_mapping = client.patch("/api/v1/supplier-product-mappings/999999", json={"priority": 1})
    assert nf_mapping.status_code == 404
    assert nf_mapping.json()["detail"]["code"] == "SUPPLIER_PRODUCT_NOT_FOUND"

    invalid = client.patch("/api/v1/supplier-product-mappings/999999", json={"lead_time_days": -1})
    assert invalid.status_code == 422


def test_shared_mapping_visible_from_supplier_and_product_views():
    supplier_id = _seed_supplier("SUP-MAP-C")
    product_id = _seed_product("SKU-MAP-C")
    client = _client()

    created = client.post(
        "/api/v1/supplier-product-mappings",
        json={"supplier_id": supplier_id, "product_id": product_id, "priority": 10},
    )
    assert created.status_code == 201
    mapping_id = created.json()["id"]

    supplier_view = client.get(f"/api/v1/suppliers/{supplier_id}/products")
    assert supplier_view.status_code == 200
    assert any(row["id"] == mapping_id for row in supplier_view.json())

    product_view = client.get(f"/api/v1/supplier-product-mappings?product_id={product_id}")
    assert product_view.status_code == 200
    assert any(row["id"] == mapping_id for row in product_view.json())

    product_detail_view = client.get(f"/api/v1/supplier-product-mappings/products/{product_id}")
    assert product_detail_view.status_code == 200
    assert any(row["id"] == mapping_id for row in product_detail_view.json())

    # update via supplier-side endpoint
    updated_supplier_side = client.patch(
        f"/api/v1/suppliers/{supplier_id}/products/{product_id}",
        json={"priority": 3, "note": "supplier-side"},
    )
    assert updated_supplier_side.status_code == 200

    reflected_product_side = client.get(f"/api/v1/supplier-product-mappings?product_id={product_id}")
    assert reflected_product_side.status_code == 200
    row = [x for x in reflected_product_side.json() if x["id"] == mapping_id][0]
    assert row["priority"] == 3
    assert row["note"] == "supplier-side"

    # update via common(flat) endpoint
    updated_flat = client.patch(f"/api/v1/supplier-product-mappings/{mapping_id}", json={"priority": 1, "note": "flat"})
    assert updated_flat.status_code == 200

    reflected_supplier_side = client.get(f"/api/v1/suppliers/{supplier_id}/products")
    assert reflected_supplier_side.status_code == 200
    row2 = [x for x in reflected_supplier_side.json() if x["id"] == mapping_id][0]
    assert row2["priority"] == 1
    assert row2["note"] == "flat"
