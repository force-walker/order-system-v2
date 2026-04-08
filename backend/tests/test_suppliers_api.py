from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.entities import (
    Customer,
    Order,
    OrderItem,
    OrderStatus,
    PricingBasis,
    Product,
    PurchaseResult,
    PurchaseResultStatus,
    Supplier,
    SupplierAllocation,
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


def _seed_allocation_reference_supplier(supplier_id: int) -> None:
    db = TestingSessionLocal()

    c = Customer(customer_code=f"C-SUP-{datetime.now(UTC).timestamp()}", name="C", active=True)
    db.add(c)
    db.flush()

    p = Product(
        sku=f"SKU-SUP-{datetime.now(UTC).timestamp()}",
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
        order_no=f"ORD-SUP-{datetime.now(UTC).timestamp()}",
        customer_id=c.id,
        order_datetime=datetime.now(UTC),
        delivery_date=datetime.now(UTC).date(),
        status=OrderStatus.confirmed,
        note=None,
    )
    db.add(o)
    db.flush()

    item = OrderItem(
        order_id=o.id,
        product_id=p.id,
        ordered_qty=1,
        pricing_basis=PricingBasis.uom_count,
        unit_price_uom_count=100,
        unit_price_uom_kg=None,
    )
    db.add(item)
    db.flush()

    db.add(
        SupplierAllocation(
            order_item_id=item.id,
            suggested_supplier_id=supplier_id,
            final_supplier_id=supplier_id,
            suggested_qty=1,
            final_qty=1,
            final_uom="count",
        )
    )
    db.commit()
    db.close()


def _seed_purchase_result_reference_supplier(supplier_id: int) -> None:
    db = TestingSessionLocal()

    c = Customer(customer_code=f"C-SUP-PR-{datetime.now(UTC).timestamp()}", name="C", active=True)
    db.add(c)
    db.flush()

    p = Product(
        sku=f"SKU-SUP-PR-{datetime.now(UTC).timestamp()}",
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
        order_no=f"ORD-SUP-PR-{datetime.now(UTC).timestamp()}",
        customer_id=c.id,
        order_datetime=datetime.now(UTC),
        delivery_date=datetime.now(UTC).date(),
        status=OrderStatus.confirmed,
        note=None,
    )
    db.add(o)
    db.flush()

    item = OrderItem(
        order_id=o.id,
        product_id=p.id,
        ordered_qty=1,
        pricing_basis=PricingBasis.uom_count,
        unit_price_uom_count=100,
        unit_price_uom_kg=None,
    )
    db.add(item)
    db.flush()

    alloc = SupplierAllocation(
        order_item_id=item.id,
        suggested_supplier_id=supplier_id,
        final_supplier_id=supplier_id,
        suggested_qty=1,
        final_qty=1,
        final_uom="count",
    )
    db.add(alloc)
    db.flush()

    db.add(
        PurchaseResult(
            allocation_id=alloc.id,
            supplier_id=supplier_id,
            purchased_qty=1,
            purchased_uom="count",
            result_status=PurchaseResultStatus.filled,
            invoiceable_flag=True,
            recorded_by="tester",
        )
    )

    db.commit()
    db.close()


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


def test_delete_supplier_soft_delete_and_not_found():
    supplier_id = _seed_supplier("SUP-DEL")
    client = _client()

    deleted = client.delete(f"/api/v1/suppliers/{supplier_id}")
    assert deleted.status_code == 204

    detail = client.get(f"/api/v1/suppliers/{supplier_id}")
    assert detail.status_code == 200
    assert detail.json()["active"] is False

    # idempotent soft delete
    deleted_again = client.delete(f"/api/v1/suppliers/{supplier_id}")
    assert deleted_again.status_code == 204

    nf = client.delete("/api/v1/suppliers/999999")
    assert nf.status_code == 404
    assert nf.json()["detail"]["code"] == "SUPPLIER_NOT_FOUND"


def test_delete_supplier_in_use_by_allocation_is_allowed_with_soft_delete():
    supplier_id = _seed_supplier("SUP-USED-ALLOC")
    _seed_allocation_reference_supplier(supplier_id)
    client = _client()

    deleted = client.delete(f"/api/v1/suppliers/{supplier_id}")
    assert deleted.status_code == 204

    detail = client.get(f"/api/v1/suppliers/{supplier_id}")
    assert detail.status_code == 200
    assert detail.json()["active"] is False


def test_delete_supplier_in_use_by_purchase_result_is_allowed_with_soft_delete():
    supplier_id = _seed_supplier("SUP-USED-PR")
    _seed_purchase_result_reference_supplier(supplier_id)
    client = _client()

    deleted = client.delete(f"/api/v1/suppliers/{supplier_id}")
    assert deleted.status_code == 204

    detail = client.get(f"/api/v1/suppliers/{supplier_id}")
    assert detail.status_code == 200
    assert detail.json()["active"] is False


def test_list_suppliers_filters_and_paging():
    _seed_supplier("SUP-FLT-001")
    s2 = _seed_supplier("SUP-FLT-002")
    s3 = _seed_supplier("SUP-FLT-003")

    client = _client()
    client.patch(f"/api/v1/suppliers/{s2}", json={"name": "Fresh Supplier", "active": False})
    client.patch(f"/api/v1/suppliers/{s3}", json={"name": "Frozen Supplier", "active": True})

    by_q = client.get("/api/v1/suppliers?q=Frozen")
    assert by_q.status_code == 200
    assert all("Frozen" in row["name"] for row in by_q.json())

    by_active = client.get("/api/v1/suppliers?active=false")
    assert by_active.status_code == 200
    assert all(row["active"] is False for row in by_active.json())

    paged = client.get("/api/v1/suppliers?limit=1&offset=1")
    assert paged.status_code == 200
    assert len(paged.json()) == 1


def _seed_product(sku: str = "SKU-SP-001") -> int:
    db = TestingSessionLocal()
    row = Product(
        sku=sku,
        name="P",
        order_uom="count",
        purchase_uom="count",
        invoice_uom="count",
        is_catch_weight=False,
        weight_capture_required=False,
        pricing_basis_default=PricingBasis.uom_count,
        active=True,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    pid = row.id
    db.close()
    return pid


def test_supplier_products_create_list_delete_flow():
    supplier_id = _seed_supplier("SUP-PROD-1")
    product_id = _seed_product("SKU-SP-100")
    client = _client()

    created = client.post(
        f"/api/v1/suppliers/{supplier_id}/products",
        json={"product_id": product_id, "priority": 10, "is_preferred": True, "note": "main"},
    )
    assert created.status_code == 201
    assert created.json()["supplier_id"] == supplier_id
    assert created.json()["product_id"] == product_id

    dup = client.post(
        f"/api/v1/suppliers/{supplier_id}/products",
        json={"product_id": product_id, "priority": 20},
    )
    assert dup.status_code == 409
    assert dup.json()["detail"]["code"] == "SUPPLIER_PRODUCT_ALREADY_EXISTS"

    listed = client.get(f"/api/v1/suppliers/{supplier_id}/products")
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    deleted = client.delete(f"/api/v1/suppliers/{supplier_id}/products/{product_id}")
    assert deleted.status_code == 204

    nf = client.delete(f"/api/v1/suppliers/{supplier_id}/products/{product_id}")
    assert nf.status_code == 404
    assert nf.json()["detail"]["code"] == "SUPPLIER_PRODUCT_NOT_FOUND"


def test_supplier_products_not_found_paths():
    supplier_id = _seed_supplier("SUP-PROD-NF")
    product_id = _seed_product("SKU-SP-200")
    client = _client()

    nf_supplier = client.post("/api/v1/suppliers/999999/products", json={"product_id": product_id})
    assert nf_supplier.status_code == 404
    assert nf_supplier.json()["detail"]["code"] == "SUPPLIER_NOT_FOUND"

    nf_product = client.post(f"/api/v1/suppliers/{supplier_id}/products", json={"product_id": 999999})
    assert nf_product.status_code == 404
    assert nf_product.json()["detail"]["code"] == "PRODUCT_NOT_FOUND"
