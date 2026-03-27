from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

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


def _seed_allocation() -> int:
    db = TestingSessionLocal()
    c = Customer(customer_code=f"C-{datetime.now(UTC).timestamp()}", name="C", active=True, created_at=datetime.now(UTC), updated_at=datetime.now(UTC))
    db.add(c)
    db.flush()

    p = Product(
        sku=f"S-{datetime.now(UTC).timestamp()}",
        name="P",
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
    db.flush()

    o = Order(
        order_no=f"O-{datetime.now(UTC).timestamp()}",
        customer_id=c.id,
        order_datetime=datetime.now(UTC),
        delivery_date=datetime.now(UTC).date(),
        status=OrderStatus.confirmed,
        note=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db.add(o)
    db.flush()

    item = OrderItem(
        order_id=o.id,
        product_id=p.id,
        ordered_qty=3,
        pricing_basis=PricingBasis.uom_count,
        unit_price_uom_count=10,
        unit_price_uom_kg=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db.add(item)
    db.flush()

    alloc = SupplierAllocation(
        order_item_id=item.id,
        suggested_supplier_id=100,
        suggested_qty=3,
        target_price=10,
        final_qty=3,
        final_uom="count",
    )
    db.add(alloc)
    db.commit()
    aid = alloc.id
    db.close()
    return aid


def test_allocation_override_and_split():
    aid = _seed_allocation()
    client = _client()

    ov = client.patch(
        f"/api/v1/allocations/{aid}/override",
        json={"final_supplier_id": 101, "final_qty": 2, "final_uom": "count", "override_reason_code": "manual"},
    )
    assert ov.status_code == 200
    assert ov.json()["final_supplier_id"] == 101

    sp = client.post(
        f"/api/v1/allocations/{aid}/split-line",
        json={
            "parts": [
                {"final_supplier_id": 201, "final_qty": 1, "final_uom": "count"},
                {"final_supplier_id": 202, "final_qty": 1, "final_uom": "count"},
            ],
            "override_reason_code": "split",
        },
    )
    assert sp.status_code == 200
    assert isinstance(sp.json(), list)
    assert len(sp.json()) == 2

    for child in sp.json():
        assert child["is_split_child"] is True
        assert child["parent_allocation_id"] == aid
        assert child["split_group_id"] is not None
        assert child["suggested_supplier_id"] == 100
        assert float(child["suggested_qty"]) == 3.0
        assert float(child["target_price"]) == 10.0


def test_allocation_validation_error_is_422():
    aid = _seed_allocation()
    client = _client()
    bad = client.patch(
        f"/api/v1/allocations/{aid}/override",
        json={"final_supplier_id": 101, "final_qty": 0, "final_uom": "count", "override_reason_code": "manual"},
    )
    assert bad.status_code == 422


def test_purchase_result_create_update_bulk_upsert():
    aid = _seed_allocation()
    client = _client()

    created = client.post(
        "/api/v1/purchase-results",
        json={
            "allocation_id": aid,
            "purchased_qty": 2,
            "purchased_uom": "count",
            "result_status": "filled",
            "invoiceable_flag": True,
        },
    )
    assert created.status_code == 201
    rid = created.json()["id"]

    dup = client.post(
        "/api/v1/purchase-results",
        json={
            "allocation_id": aid,
            "purchased_qty": 2,
            "purchased_uom": "count",
            "result_status": "filled",
            "invoiceable_flag": True,
        },
    )
    assert dup.status_code == 409
    assert dup.json()["detail"]["code"] == "PURCHASE_RESULT_ALREADY_EXISTS"

    upd = client.patch(f"/api/v1/purchase-results/{rid}", json={"result_status": "partially_filled"})
    assert upd.status_code == 200
    assert upd.json()["result_status"] == "partially_filled"

    upsert = client.post(
        "/api/v1/purchase-results/bulk-upsert",
        json={
            "items": [
                {
                    "allocation_id": aid,
                    "purchased_qty": 2,
                    "purchased_uom": "count",
                    "result_status": "filled",
                    "invoiceable_flag": True,
                }
            ]
        },
    )
    assert upsert.status_code == 200
    assert upsert.json()["upserted_count"] == 1
