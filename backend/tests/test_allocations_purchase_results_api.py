from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.entities import Customer, Order, OrderItem, OrderStatus, PricingBasis, Product, Supplier, SupplierAllocation


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


def _seed_allocation(final_qty: float = 3, final_supplier_id: int | None = None, suggested_supplier_id: int | None = 100) -> int:
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
        suggested_supplier_id=suggested_supplier_id,
        suggested_qty=3,
        target_price=10,
        final_supplier_id=final_supplier_id,
        final_qty=final_qty,
        final_uom="count",
    )
    db.add(alloc)
    db.commit()
    aid = alloc.id
    db.close()
    return aid


def _seed_supplier(name: str = "Supplier A") -> int:
    db = TestingSessionLocal()
    row = Supplier(supplier_code=f"S-{datetime.now(UTC).timestamp()}", name=name, active=True)
    db.add(row)
    db.commit()
    db.refresh(row)
    sid = row.id
    db.close()
    return sid


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
        json={"final_supplier_id": 101, "final_qty": -1, "final_uom": "count", "override_reason_code": "manual"},
    )
    assert bad.status_code == 422


def test_purchase_result_create_get_list_update_bulk_upsert():
    aid = _seed_allocation(final_qty=10)
    client = _client()

    created = client.post(
        "/api/v1/purchase-results",
        json={
            "allocation_id": aid,
            "supplier_id": 555,
            "purchased_qty": 2,
            "purchased_uom": "count",
            "actual_weight_kg": 2.5,
            "unit_cost": 100,
            "final_unit_cost": 120,
            "shortage_qty": 0,
            "shortage_policy": "backorder",
            "result_status": "filled",
            "invoiceable_flag": True,
            "recorded_by": "tester",
        },
    )
    assert created.status_code == 201
    rid = created.json()["id"]
    assert created.json()["supplier_id"] == 555
    assert float(created.json()["actual_weight_kg"]) == 2.5
    assert float(created.json()["unit_cost"]) == 100.0
    assert created.json()["recorded_by"] == "tester"

    got = client.get(f"/api/v1/purchase-results/{rid}")
    assert got.status_code == 200
    assert got.json()["id"] == rid

    listed = client.get(f"/api/v1/purchase-results?allocation_id={aid}")
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    dup = client.post(
        "/api/v1/purchase-results",
        json={
            "allocation_id": aid,
            "purchased_qty": 2,
            "purchased_uom": "count",
            "result_status": "partially_filled",
            "invoiceable_flag": True,
        },
    )
    assert dup.status_code == 201

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


def test_purchase_result_defaults_supplier_from_allocation():
    aid = _seed_allocation(final_qty=3, final_supplier_id=777, suggested_supplier_id=100)
    client = _client()

    created = client.post(
        "/api/v1/purchase-results",
        json={
            "allocation_id": aid,
            "purchased_qty": 1,
            "purchased_uom": "count",
            "result_status": "filled",
            "invoiceable_flag": True,
        },
    )
    assert created.status_code == 201
    assert created.json()["supplier_id"] == 777


def test_purchase_result_quantity_limit_is_422():
    aid = _seed_allocation(final_qty=3)
    client = _client()

    first = client.post(
        "/api/v1/purchase-results",
        json={
            "allocation_id": aid,
            "purchased_qty": 2,
            "purchased_uom": "count",
            "result_status": "filled",
            "invoiceable_flag": True,
        },
    )
    assert first.status_code == 201

    second = client.post(
        "/api/v1/purchase-results",
        json={
            "allocation_id": aid,
            "purchased_qty": 2,
            "purchased_uom": "count",
            "result_status": "partially_filled",
            "invoiceable_flag": True,
        },
    )
    assert second.status_code == 422
    assert second.json()["detail"]["code"] == "PURCHASE_QTY_EXCEEDS_ALLOCATION"


def test_purchase_result_list_filters_supplier_and_paging():
    aid = _seed_allocation(final_qty=10)
    client = _client()

    for supplier_id in [101, 102, 101]:
        created = client.post(
            "/api/v1/purchase-results",
            json={
                "allocation_id": aid,
                "supplier_id": supplier_id,
                "purchased_qty": 1,
                "purchased_uom": "count",
                "result_status": "filled",
                "invoiceable_flag": True,
            },
        )
        assert created.status_code == 201

    all_rows = client.get(f"/api/v1/purchase-results?allocation_id={aid}")
    assert all_rows.status_code == 200
    assert len(all_rows.json()) == 3

    filtered = client.get(f"/api/v1/purchase-results?allocation_id={aid}&supplier_id=101")
    assert filtered.status_code == 200
    assert len(filtered.json()) == 2
    assert all(row["supplier_id"] == 101 for row in filtered.json())

    paged = client.get(f"/api/v1/purchase-results?allocation_id={aid}&limit=1&offset=1")
    assert paged.status_code == 200
    assert len(paged.json()) == 1


def test_purchase_result_list_returns_supplier_and_invoice_defaults_and_filter_sort():
    aid = _seed_allocation(final_qty=10)
    supplier_a = _seed_supplier("Supplier A")
    supplier_b = _seed_supplier("Supplier B")
    client = _client()

    c1 = client.post(
        "/api/v1/purchase-results",
        json={
            "allocation_id": aid,
            "supplier_id": supplier_a,
            "purchased_qty": 1,
            "purchased_uom": "count",
            "result_status": "filled",
            "invoiceable_flag": True,
        },
    )
    assert c1.status_code == 201

    c2 = client.post(
        "/api/v1/purchase-results",
        json={
            "allocation_id": aid,
            "supplier_id": supplier_b,
            "purchased_qty": 1,
            "purchased_uom": "count",
            "result_status": "partially_filled",
            "invoiceable_flag": True,
        },
    )
    assert c2.status_code == 201

    listed = client.get("/api/v1/purchase-results")
    assert listed.status_code == 200
    row = listed.json()[0]
    assert "supplier_id" in row
    assert "supplier_name" in row
    assert row["invoice_qty"] is None
    assert row["invoice_uom"] is not None
    assert row["received_qty"] == row["purchased_qty"]
    assert row["order_uom"] == row["purchased_uom"]

    filtered_supplier = client.get(f"/api/v1/purchase-results?supplier_id={supplier_a}")
    assert filtered_supplier.status_code == 200
    assert len(filtered_supplier.json()) == 1
    assert filtered_supplier.json()[0]["supplier_id"] == supplier_a
    assert filtered_supplier.json()[0]["supplier_name"] == "Supplier A"

    cid = row["customer_id"]
    pid = row["product_id"]
    filtered_cp = client.get(f"/api/v1/purchase-results?customer_id={cid}&product_id={pid}")
    assert filtered_cp.status_code == 200
    assert len(filtered_cp.json()) == 2

    sorted_supplier_desc = client.get("/api/v1/purchase-results?sort_by=supplier&sort_order=desc")
    assert sorted_supplier_desc.status_code == 200
    named_rows = [r for r in sorted_supplier_desc.json() if r.get("supplier_name") is not None]
    names = [r["supplier_name"] for r in named_rows]
    assert names == sorted(names, reverse=True)


def test_purchase_result_defer_and_undefer():
    aid = _seed_allocation(final_qty=5)
    client = _client()

    created = client.post(
        "/api/v1/purchase-results",
        json={
            "allocation_id": aid,
            "supplier_id": 101,
            "purchased_qty": 1,
            "purchased_uom": "count",
            "result_status": "filled",
            "invoiceable_flag": True,
        },
    )
    assert created.status_code == 201
    rid = created.json()["id"]

    deferred = client.post(
        f"/api/v1/purchase-results/{rid}/defer",
        json={"defer_reason": "later", "deferred_by": "tester"},
    )
    assert deferred.status_code == 200
    assert deferred.json()["is_deferred"] is True
    assert deferred.json()["defer_reason"] == "later"

    undeferred = client.post(f"/api/v1/purchase-results/{rid}/undefer")
    assert undeferred.status_code == 200
    assert undeferred.json()["is_deferred"] is False
    assert undeferred.json()["defer_reason"] is None


def test_purchase_result_work_queue_and_history_separation():
    aid = _seed_allocation(final_qty=10)
    client = _client()

    active = client.post(
        "/api/v1/purchase-results",
        json={
            "allocation_id": aid,
            "supplier_id": 501,
            "purchased_qty": 1,
            "purchased_uom": "count",
            "result_status": "filled",
            "invoiceable_flag": True,
        },
    )
    assert active.status_code == 201
    active_id = active.json()["id"]

    deferred = client.post(
        "/api/v1/purchase-results",
        json={
            "allocation_id": aid,
            "supplier_id": 502,
            "purchased_qty": 1,
            "purchased_uom": "count",
            "result_status": "partially_filled",
            "invoiceable_flag": True,
        },
    )
    assert deferred.status_code == 201
    deferred_id = deferred.json()["id"]

    defer_res = client.post(
        f"/api/v1/purchase-results/{deferred_id}/defer",
        json={"defer_reason": "postpone", "deferred_by": "tester"},
    )
    assert defer_res.status_code == 200

    target_date = active.json()["recorded_at"][:10]
    work = client.get(f"/api/v1/purchase-results/queue/work-queue?target_date={target_date}")
    assert work.status_code == 200
    work_ids = {r["id"] for r in work.json()}
    assert active_id in work_ids
    assert deferred_id not in work_ids

    hist = client.get("/api/v1/purchase-results/queue/history")
    assert hist.status_code == 200
    hist_ids = {r["id"] for r in hist.json()}
    assert active_id in hist_ids
    assert deferred_id in hist_ids


def test_purchase_result_invoice_qty_persists_after_save():
    aid = _seed_allocation(final_qty=10)
    client = _client()

    created = client.post(
        "/api/v1/purchase-results",
        json={
            "allocation_id": aid,
            "supplier_id": 600,
            "purchased_qty": 2,
            "purchased_uom": "count",
            "invoice_qty": 3,
            "result_status": "filled",
            "invoiceable_flag": True,
        },
    )
    assert created.status_code == 201
    rid = created.json()["id"]
    assert float(created.json()["invoice_qty"]) == 3.0

    got = client.get(f"/api/v1/purchase-results/{rid}")
    assert got.status_code == 200
    assert float(got.json()["invoice_qty"]) == 3.0

    listed = client.get(f"/api/v1/purchase-results?allocation_id={aid}")
    assert listed.status_code == 200
    assert any(float(r["invoice_qty"]) == 3.0 for r in listed.json() if r["id"] == rid)


def test_purchase_result_unit_cost_negative_is_422():
    aid = _seed_allocation(final_qty=5)
    client = _client()

    bad = client.post(
        "/api/v1/purchase-results",
        json={
            "allocation_id": aid,
            "purchased_qty": 1,
            "purchased_uom": "count",
            "unit_cost": -1,
            "result_status": "filled",
            "invoiceable_flag": True,
        },
    )
    assert bad.status_code == 422
