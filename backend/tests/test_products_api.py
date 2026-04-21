from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.entities import Customer, Order, OrderItem, OrderStatus, PricingBasis, Product


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
        "legacy_code": "L-001",
        "legacy_unit_code": "U-01",
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
    assert created.json()["legacy_code"] == "L-001"
    assert created.json()["legacy_unit_code"] == "U-01"

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

    ok = client.patch(
        f"/api/v1/products/{pid}",
        json={"name": "Updated Name", "legacy_code": "L-UPD", "legacy_unit_code": "U-UPD", "active": False},
    )
    assert ok.status_code == 200
    assert ok.json()["name"] == "Updated Name"
    assert ok.json()["legacy_code"] == "L-UPD"
    assert ok.json()["legacy_unit_code"] == "U-UPD"
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


def _seed_order_item_reference(product_id: int) -> None:
    db = TestingSessionLocal()
    customer = Customer(customer_code=f"C-P-{datetime.now(UTC).timestamp()}", name="C", active=True)
    db.add(customer)
    db.flush()

    order = Order(
        order_no=f"ORD-P-{datetime.now(UTC).timestamp()}",
        customer_id=customer.id,
        order_datetime=datetime.now(UTC),
        delivery_date=datetime.now(UTC).date(),
        status=OrderStatus.confirmed,
        note=None,
    )
    db.add(order)
    db.flush()

    db.add(
        OrderItem(
            order_id=order.id,
            product_id=product_id,
            ordered_qty=1,
            pricing_basis=PricingBasis.uom_count,
            unit_price_uom_count=100,
            unit_price_uom_kg=None,
        )
    )
    db.commit()
    db.close()


def test_archive_and_list_filters_include_inactive():
    pid = _seed_product("SKU-ARCHIVE")
    client = _client()

    archived = client.post(f"/api/v1/products/{pid}/archive")
    assert archived.status_code == 200
    assert archived.json()["active"] is False

    listed_default = client.get("/api/v1/products")
    assert listed_default.status_code == 200
    assert all(row["id"] != pid for row in listed_default.json())

    listed_all = client.get("/api/v1/products?include_inactive=true")
    assert listed_all.status_code == 200
    assert any(row["id"] == pid for row in listed_all.json())


def test_delete_product_in_use_is_409_and_no_ref_is_204():
    in_use_pid = _seed_product("SKU-IN-USE")
    _seed_order_item_reference(in_use_pid)
    client = _client()

    blocked = client.delete(f"/api/v1/products/{in_use_pid}")
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "PRODUCT_IN_USE"

    free_pid = _seed_product("SKU-FREE")
    deleted = client.delete(f"/api/v1/products/{free_pid}")
    assert deleted.status_code == 204


def test_import_upsert_products_create_success():
    client = _client()
    res = client.post(
        "/api/v1/products/import-upsert",
        json={
            "items": [
                {
                    "import_key": "IMP-001",
                    "name": "Imported Product",
                    "order_uom": "count",
                    "purchase_uom": "count",
                    "invoice_uom": "count",
                }
            ]
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 1
    assert body["created"] == 1
    assert body["updated"] == 0
    assert body["failed"] == 0


def test_import_upsert_products_import_key_update_success():
    client = _client()

    created = client.post(
        "/api/v1/products/import-upsert",
        json={
            "items": [
                {
                    "import_key": "IMP-UPD-001",
                    "name": "Before Update",
                    "order_uom": "count",
                    "purchase_uom": "count",
                    "invoice_uom": "count",
                }
            ]
        },
    )
    assert created.status_code == 200

    updated = client.post(
        "/api/v1/products/import-upsert",
        json={"items": [{"import_key": "IMP-UPD-001", "name": "After Update"}]},
    )
    assert updated.status_code == 200
    body = updated.json()
    assert body["created"] == 0
    assert body["updated"] == 1


def test_import_upsert_products_create_required_missing_is_failed():
    client = _client()
    res = client.post(
        "/api/v1/products/import-upsert",
        json={"items": [{"import_key": "IMP-MISS-001", "name": "Missing UOM"}]},
    )

    assert res.status_code == 200
    body = res.json()
    assert body["created"] == 0
    assert body["failed"] == 1
    assert body["errors"][0]["action"] == "create"
    assert body["errors"][0]["code"] == "REQUIRED_FIELDS_MISSING"


def test_import_upsert_products_partial_update_keeps_unspecified_and_null_fields():
    client = _client()

    created = client.post(
        "/api/v1/products/import-upsert",
        json={
            "items": [
                {
                    "import_key": "IMP-PARTIAL-001",
                    "name": "Partial Base",
                    "legacy_code": "LEG-BASE",
                    "order_uom": "count",
                    "purchase_uom": "count",
                    "invoice_uom": "count",
                }
            ]
        },
    )
    assert created.status_code == 200

    updated = client.post(
        "/api/v1/products/import-upsert",
        json={"items": [{"import_key": "IMP-PARTIAL-001", "name": "Partial Updated", "legacy_code": ""}]},
    )
    assert updated.status_code == 200
    assert updated.json()["updated"] == 1

    listed = client.get("/api/v1/products?include_inactive=true")
    rows = [r for r in listed.json() if r.get("import_key") == "IMP-PARTIAL-001"]
    assert len(rows) == 1
    row = rows[0]
    assert row["name"] == "Partial Updated"
    assert row["legacy_code"] == "LEG-BASE"


def test_import_upsert_products_duplicate_import_key_conflict_in_payload():
    client = _client()
    res = client.post(
        "/api/v1/products/import-upsert",
        json={
            "items": [
                {
                    "import_key": "IMP-DUP-001",
                    "name": "A",
                    "order_uom": "count",
                    "purchase_uom": "count",
                    "invoice_uom": "count",
                },
                {
                    "import_key": "IMP-DUP-001",
                    "name": "B",
                    "order_uom": "count",
                    "purchase_uom": "count",
                    "invoice_uom": "count",
                },
            ]
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["failed"] == 1
    assert body["errors"][0]["code"] == "DUPLICATE_IMPORT_KEY_IN_PAYLOAD"


def test_import_upsert_products_invalid_numeric_is_row_error_and_empty_string_is_null():
    client = _client()
    res = client.post(
        "/api/v1/products/import-upsert",
        json={
            "items": [
                {
                    "import_key": "IMP-NUM-001",
                    "name": "Num Test",
                    "order_uom": "count",
                    "purchase_uom": "count",
                    "invoice_uom": "count",
                    "sales_price": "not-number",
                },
                {
                    "import_key": "IMP-NUM-002",
                    "name": "Num Test2",
                    "order_uom": "count",
                    "purchase_uom": "count",
                    "invoice_uom": "count",
                    "sales_price": "",
                },
            ]
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["failed"] == 1
    assert body["created"] == 1
    assert body["errors"][0]["code"] == "ITEM_VALIDATION_ERROR"
