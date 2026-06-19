from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

from app.api.routes_orders import HK_TZ, _default_delivery_date_by_hk_time, _stale_cutoff_delivery_date

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.entities import Customer, LineStatus, Order, OrderItem, OrderStatus, PricingBasis, Product


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
        customer_code=code,
        name="Test Customer",
        active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
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
    assert any(x["customer_code"] == "CUST-LIST" for x in res.json())


def test_create_customer_auto_code_and_manual_code_rejected():
    client = _client()

    created = client.post("/api/v1/customers", json={"region": "HK", "name": "New Customer", "active": True})
    assert created.status_code == 201
    assert created.json()["customer_code"].startswith("CUST-")
    assert created.json()["region"] == "HK"

    manual = client.post("/api/v1/customers", json={"customer_code": "CUST-MANUAL", "name": "Manual", "active": True})
    assert manual.status_code == 422


def test_update_customer_success_and_not_found():
    cid = _seed_customer("CUST-UPD")
    client = _client()

    ok = client.patch(f"/api/v1/customers/{cid}", json={"name": "Updated Customer", "active": False})
    assert ok.status_code == 200
    assert ok.json()["name"] == "Updated Customer"
    assert ok.json()["active"] is False

    nf = client.patch("/api/v1/customers/999999", json={"name": "x"})
    assert nf.status_code == 404
    assert nf.json()["detail"]["code"] == "CUSTOMER_NOT_FOUND"


def test_create_customer_validation_error_is_422():
    client = _client()
    res = client.post("/api/v1/customers", json={})
    assert res.status_code == 422


def test_create_customer_auto_code_generation_is_sequential():
    client = _client()

    first = client.post("/api/v1/customers", json={"name": "Auto Customer 1", "active": True})
    second = client.post("/api/v1/customers", json={"name": "Auto Customer 2", "active": True})

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["customer_code"].startswith("CUST-")
    assert second.json()["customer_code"].startswith("CUST-")

    n1 = int(first.json()["customer_code"].split("-")[-1])
    n2 = int(second.json()["customer_code"].split("-")[-1])
    assert n2 == n1 + 1


def test_get_customer_not_found():
    client = _client()
    res = client.get("/api/v1/customers/999999")
    assert res.status_code == 404
    assert res.json()["detail"]["code"] == "CUSTOMER_NOT_FOUND"


def test_customer_archive_and_include_inactive_filter():
    cid = _seed_customer("CUST-ARCH")
    client = _client()

    archived = client.post(f"/api/v1/customers/{cid}/archive")
    assert archived.status_code == 200
    assert archived.json()["active"] is False

    listed_default = client.get("/api/v1/customers")
    assert listed_default.status_code == 200
    assert all(row["id"] != cid for row in listed_default.json())

    listed_all = client.get("/api/v1/customers?include_inactive=true")
    assert listed_all.status_code == 200
    assert any(row["id"] == cid for row in listed_all.json())

    unarchived = client.post(f"/api/v1/customers/{cid}/unarchive")
    assert unarchived.status_code == 200
    assert unarchived.json()["active"] is True


def test_customer_delete_in_use_is_409_and_no_ref_is_204():
    client = _client()

    in_use_cid = _seed_customer("CUST-INUSE")
    create_order = client.post("/api/v1/orders", json={"customer_id": in_use_cid, "delivery_date": str(date.today())})
    assert create_order.status_code == 201

    blocked = client.delete(f"/api/v1/customers/{in_use_cid}")
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "CUSTOMER_IN_USE"

    free_cid = _seed_customer("CUST-FREE")
    deleted = client.delete(f"/api/v1/customers/{free_cid}")
    assert deleted.status_code == 204


def test_get_customer_import_format():
    client = _client()
    res = client.get("/api/v1/customers/import-format")
    assert res.status_code == 200
    body = res.json()
    assert body["entity"] == "customers"
    field_names = [field["name"] for field in body["fields"]]
    assert field_names == ["import_key", "region", "name", "active"]
    name_field = next(field for field in body["fields"] if field["name"] == "name")
    assert name_field["required"] is True
    assert name_field["required_scope"] == "create"


def test_import_upsert_customers_create_success():
    client = _client()
    res = client.post(
        "/api/v1/customers/import-upsert",
        json={"items": [{"import_key": "CUST-IMP-001", "region": "kanto", "name": "Imported Customer", "active": True}]},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 1
    assert body["created"] == 1
    assert body["updated"] == 0
    assert body["failed"] == 0


def test_import_upsert_customers_update_success():
    client = _client()
    created = client.post(
        "/api/v1/customers/import-upsert",
        json={"items": [{"import_key": "CUST-IMP-UPD-001", "region": "kanto", "name": "Before"}]},
    )
    assert created.status_code == 200

    updated = client.post(
        "/api/v1/customers/import-upsert",
        json={"items": [{"import_key": "CUST-IMP-UPD-001", "region": "kansai", "name": "After"}]},
    )
    assert updated.status_code == 200
    body = updated.json()
    assert body["created"] == 0
    assert body["updated"] == 1


def test_import_upsert_customers_duplicate_import_key_conflict_in_payload():
    client = _client()
    res = client.post(
        "/api/v1/customers/import-upsert",
        json={
            "items": [
                {"import_key": "CUST-IMP-DUP-001", "name": "A"},
                {"import_key": "CUST-IMP-DUP-001", "name": "B"},
            ]
        },
    )
    assert res.status_code == 200
    assert res.json()["failed"] == 1
    assert res.json()["errors"][0]["code"] == "DUPLICATE_IMPORT_KEY_IN_PAYLOAD"


def test_import_upsert_customers_create_required_missing_is_failed():
    client = _client()
    res = client.post(
        "/api/v1/customers/import-upsert",
        json={"items": [{"import_key": "CUST-IMP-MISS-001", "region": "kanto"}]},
    )
    assert res.status_code == 200
    assert res.json()["created"] == 0
    assert res.json()["failed"] == 1
    assert res.json()["errors"][0]["code"] == "REQUIRED_FIELDS_MISSING"


def test_import_upsert_customers_empty_update_is_skipped():
    client = _client()
    created = client.post(
        "/api/v1/customers/import-upsert",
        json={"items": [{"import_key": "CUST-IMP-SKIP-001", "region": "kanto", "name": "Skip Target"}]},
    )
    assert created.status_code == 200

    skipped = client.post(
        "/api/v1/customers/import-upsert",
        json={"items": [{"import_key": "CUST-IMP-SKIP-001", "region": "", "name": ""}]},
    )
    assert skipped.status_code == 200
    assert skipped.json()["skipped"] == 1


def test_import_upsert_customers_partial_failure_keeps_other_rows():
    client = _client()
    res = client.post(
        "/api/v1/customers/import-upsert",
        json={
            "items": [
                {"import_key": "CUST-IMP-PART-001", "name": "Kept Customer"},
                {"import_key": "CUST-IMP-PART-002"},
            ]
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["created"] == 1
    assert body["failed"] == 1
    assert body["errors"][0]["code"] == "REQUIRED_FIELDS_MISSING"


def test_create_order_success_and_list():
    cid = _seed_customer("CUST-ORDER")
    payload = {
        "customer_id": cid,
        "delivery_date": str(date.today()),
        "shipped_date": str(date.today()),
        "note": "first order",
    }
    client = _client()
    create_res = client.post("/api/v1/orders", json=payload)
    assert create_res.status_code == 201
    assert create_res.json()["tracking_no"] is not None
    assert len(create_res.json()["tracking_no"].split("-")) == 2
    assert create_res.json()["order_no"].startswith("ORD-")
    assert create_res.json()["created_by"] == "system_api"
    assert create_res.json()["updated_by"] == "system_api"
    assert create_res.json()["shipped_date"] == str(date.today())

    list_res = client.get("/api/v1/orders")
    assert list_res.status_code == 200
    assert any(x["id"] == create_res.json()["id"] for x in list_res.json())

    order_id = create_res.json()["id"]
    detail_res = client.get(f"/api/v1/orders/{order_id}")
    assert detail_res.status_code == 200
    assert detail_res.json()["id"] == order_id


def test_default_delivery_date_boundary_rule_hk_tz():
    assert _default_delivery_date_by_hk_time(datetime(2026, 4, 14, 15, 59, tzinfo=HK_TZ)) == date(2026, 4, 14)
    assert _default_delivery_date_by_hk_time(datetime(2026, 4, 14, 16, 0, tzinfo=HK_TZ)) == date(2026, 4, 15)
    assert _default_delivery_date_by_hk_time(datetime(2026, 4, 14, 23, 59, tzinfo=HK_TZ)) == date(2026, 4, 15)
    assert _default_delivery_date_by_hk_time(datetime(2026, 4, 14, 0, 0, tzinfo=HK_TZ)) == date(2026, 4, 14)


def test_create_order_uses_default_delivery_date_when_omitted():
    cid = _seed_customer("CUST-ORDER-DEFAULT-DATE")
    client = _client()

    created = client.post("/api/v1/orders", json={"customer_id": cid, "note": "default delivery"})
    assert created.status_code == 201
    # for test determinism we only assert non-nullness
    assert created.json()["delivery_date"] is not None


def test_create_order_allows_shipped_date_different_from_delivery_date():
    cid = _seed_customer("CUST-SHIP-DIFF")
    client = _client()

    created = client.post(
        "/api/v1/orders",
        json={"customer_id": cid, "delivery_date": "2026-04-15", "shipped_date": "2026-04-14"},
    )
    assert created.status_code == 201
    assert created.json()["delivery_date"] == "2026-04-15"
    assert created.json()["shipped_date"] == "2026-04-14"


def test_create_order_customer_not_found():
    payload = {
        "customer_id": 999999,
        "delivery_date": str(date.today()),
    }
    client = _client()
    res = client.post("/api/v1/orders", json=payload)
    assert res.status_code == 404
    assert res.json()["detail"]["code"] == "CUSTOMER_NOT_FOUND"


def test_create_order_auto_numbering_generates_unique_order_no():
    cid = _seed_customer("CUST-DUP")
    payload = {
        "customer_id": cid,
        "delivery_date": str(date.today()),
    }
    client = _client()
    first = client.post("/api/v1/orders", json=payload)
    assert first.status_code == 201

    second = client.post("/api/v1/orders", json=payload)
    assert second.status_code == 201
    assert first.json()["tracking_no"] != second.json()["tracking_no"]
    assert first.json()["order_no"] != second.json()["order_no"]


def test_update_order_header_success_and_not_found():
    cid = _seed_customer("CUST-ORD-UPD")
    cid2 = _seed_customer("CUST-ORD-UPD-2")
    client = _client()

    created = client.post(
        "/api/v1/orders",
        json={"customer_id": cid, "delivery_date": str(date.today()), "note": "before"},
    )
    assert created.status_code == 201
    oid = created.json()["id"]

    ok = client.patch(
        f"/api/v1/orders/{oid}",
        json={"customer_id": cid2, "delivery_date": str(date.today()), "shipped_date": str(date.today()), "note": "after"},
    )
    assert ok.status_code == 200
    assert ok.json()["customer_id"] == cid2
    assert ok.json()["note"] == "after"
    assert ok.json()["shipped_date"] == str(date.today())

    nf = client.patch("/api/v1/orders/999999", json={"note": "x"})
    assert nf.status_code == 404
    assert nf.json()["detail"]["code"] == "ORDER_NOT_FOUND"


def test_update_order_customer_not_found():
    cid = _seed_customer("CUST-ORD-UPD-NF")
    client = _client()
    created = client.post(
        "/api/v1/orders",
        json={"customer_id": cid, "delivery_date": str(date.today())},
    )
    oid = created.json()["id"]

    bad = client.patch(f"/api/v1/orders/{oid}", json={"customer_id": 999999})
    assert bad.status_code == 404
    assert bad.json()["detail"]["code"] == "CUSTOMER_NOT_FOUND"


def test_get_order_not_found():
    client = _client()
    res = client.get("/api/v1/orders/999999")
    assert res.status_code == 404
    assert res.json()["detail"]["code"] == "ORDER_NOT_FOUND"


def _seed_order_with_open_line() -> int:
    db = TestingSessionLocal()
    suffix = uuid4().hex[:8]

    customer = Customer(
        customer_code=f"CUST-TRANS-{suffix}",
        name="Transition Customer",
        active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db.add(customer)
    db.flush()

    product = Product(
        sku=f"SKU-TRANS-{suffix}",
        name="Transition Product",
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
    db.add(product)
    db.flush()

    order = Order(
        order_no=f"ORD-TRANS-{suffix}",
        customer_id=customer.id,
        order_datetime=datetime.now(UTC),
        delivery_date=date.today(),
        status=OrderStatus.confirmed,
        note=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db.add(order)
    db.flush()

    line = OrderItem(
        order_id=order.id,
        product_id=product.id,
        ordered_qty=2,
        pricing_basis=PricingBasis.uom_count,
        unit_price_uom_count=10,
        unit_price_uom_kg=None,
        line_status=LineStatus.open,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db.add(line)
    db.commit()
    oid = order.id
    db.close()
    return oid


def test_order_bulk_transition_success_and_no_target_lines():
    order_id = _seed_order_with_open_line()
    client = _client()

    ok = client.post(
        f"/api/v1/orders/{order_id}/bulk-transition",
        json={"from_status": "confirmed", "to_status": "allocated"},
    )
    assert ok.status_code == 200
    assert ok.json()["order_id"] == order_id
    assert ok.json()["updated_lines"] == 1
    assert ok.json()["updated_order_status"] == "allocated"

    detail_after = client.get(f"/api/v1/orders/{order_id}")
    assert detail_after.status_code == 200
    assert detail_after.json()["updated_by"] == "system_api"

    no_target = client.post(
        f"/api/v1/orders/{order_id}/bulk-transition",
        json={"from_status": "confirmed", "to_status": "allocated"},
    )
    assert no_target.status_code == 409
    assert no_target.json()["detail"]["code"] == "ORDER_STATUS_MISMATCH"


def test_order_bulk_transition_invalid_pair():
    order_id = _seed_order_with_open_line()
    client = _client()
    bad = client.post(
        f"/api/v1/orders/{order_id}/bulk-transition",
        json={"from_status": "confirmed", "to_status": "invoiced"},
    )
    assert bad.status_code == 422
    assert bad.json()["detail"]["code"] == "INVALID_TRANSITION_PAIR"


def test_order_bulk_transition_line_status_mismatch_is_409():
    order_id = _seed_order_with_open_line()
    client = _client()

    # first transition to allocated (line status becomes allocated)
    ok = client.post(
        f"/api/v1/orders/{order_id}/bulk-transition",
        json={"from_status": "confirmed", "to_status": "allocated"},
    )
    assert ok.status_code == 200

    # manually force order header back to confirmed to simulate inconsistent state
    db = TestingSessionLocal()
    order = db.query(Order).filter(Order.id == order_id).first()
    assert order is not None
    order.status = OrderStatus.confirmed
    db.commit()
    db.close()

    bad = client.post(
        f"/api/v1/orders/{order_id}/bulk-transition",
        json={"from_status": "confirmed", "to_status": "allocated"},
    )
    assert bad.status_code == 409
    assert bad.json()["detail"]["code"] == "LINE_STATUS_MISMATCH"


def test_order_bulk_transition_same_status_is_422():
    order_id = _seed_order_with_open_line()
    client = _client()
    bad = client.post(
        f"/api/v1/orders/{order_id}/bulk-transition",
        json={"from_status": "confirmed", "to_status": "confirmed"},
    )
    assert bad.status_code == 422
    assert bad.json()["detail"]["code"] == "INVALID_TRANSITION_PAIR"


def test_order_validation_required_and_enum_are_422():
    client = _client()

    missing_required = client.post(
        "/api/v1/orders",
        json={"delivery_date": str(date.today())},
    )
    assert missing_required.status_code == 422

    invalid_enum = client.post(
        "/api/v1/orders/1/bulk-transition",
        json={"from_status": "invalid_status", "to_status": "allocated"},
    )
    assert invalid_enum.status_code == 422


def _seed_order_with_status_and_delivery(status: OrderStatus, delivery: date) -> int:
    db = TestingSessionLocal()
    suffix = uuid4().hex[:8]

    customer = Customer(
        customer_code=f"CUST-CANCEL-{suffix}",
        name="Cancel Customer",
        active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db.add(customer)
    db.flush()

    order = Order(
        order_no=f"ORD-CANCEL-{suffix}",
        customer_id=customer.id,
        order_datetime=datetime.now(UTC),
        delivery_date=delivery,
        status=status,
        note=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db.add(order)
    db.commit()
    oid = order.id
    db.close()
    return oid


def test_stale_cutoff_boundary_hk_tz():
    assert _stale_cutoff_delivery_date(datetime(2026, 4, 14, 0, 0, tzinfo=HK_TZ)) == date(2026, 4, 14)
    assert _stale_cutoff_delivery_date(datetime(2026, 4, 14, 15, 59, tzinfo=HK_TZ)) == date(2026, 4, 14)
    assert _stale_cutoff_delivery_date(datetime(2026, 4, 14, 16, 0, tzinfo=HK_TZ)) == date(2026, 4, 15)
    assert _stale_cutoff_delivery_date(datetime(2026, 4, 14, 23, 59, tzinfo=HK_TZ)) == date(2026, 4, 15)


def _seed_order_item_for_label(customer_name: str = "Label Customer", product_name: str = "Label Product", note: str = "item memo") -> int:
    db = TestingSessionLocal()
    customer = Customer(customer_code=f"CUST-LABEL-{uuid4().hex[:6]}", region="HK", name=customer_name, active=True)
    db.add(customer)
    db.flush()

    product = Product(
        sku=f"SKU-LABEL-{uuid4().hex[:6]}",
        name=product_name,
        order_uom="count",
        purchase_uom="count",
        invoice_uom="count",
        pricing_basis_default=PricingBasis.uom_count,
        is_catch_weight=False,
        weight_capture_required=False,
        active=True,
    )
    db.add(product)
    db.flush()

    order = Order(
        order_no=f"ORD-LABEL-{uuid4().hex[:6]}",
        customer_id=customer.id,
        order_datetime=datetime.now(UTC),
        delivery_date=date.today(),
        shipped_date=date.today(),
        status=OrderStatus.confirmed,
        note="label note",
    )
    db.add(order)
    db.flush()

    item = OrderItem(
        order_id=order.id,
        product_id=product.id,
        ordered_qty=3,
        pricing_basis=PricingBasis.uom_count,
        order_uom_type=PricingBasis.uom_count,
        unit_price_uom_count=100,
        unit_price_uom_kg=None,
        note=note,
    )
    db.add(item)
    db.commit()
    iid = item.id
    db.close()
    return iid


def test_list_orders_stale_filter():
    client = _client()

    today = date.today()
    yesterday = today - timedelta(days=1)
    old_id = _seed_order_with_status_and_delivery(OrderStatus.confirmed, yesterday)
    today_id = _seed_order_with_status_and_delivery(OrderStatus.confirmed, today)
    shipped_old_id = _seed_order_with_status_and_delivery(OrderStatus.shipped, yesterday)

    stale = client.get("/api/v1/orders?stale_delivery_only=true")
    assert stale.status_code == 200
    stale_ids = {row["id"] for row in stale.json()}

    assert old_id in stale_ids

    # cutoff depends on current HK time (16:00 boundary)
    cutoff = _stale_cutoff_delivery_date(datetime.now(HK_TZ))
    if today < cutoff:
        assert today_id in stale_ids
    else:
        assert today_id not in stale_ids

    assert shipped_old_id not in stale_ids


def test_bulk_cancel_orders_success_and_partial_failure():
    client = _client()
    d = date.today()
    ok_order = _seed_order_with_status_and_delivery(OrderStatus.confirmed, d)
    ng_order = _seed_order_with_status_and_delivery(OrderStatus.shipped, d)

    res = client.post(
        "/api/v1/orders/bulk-cancel",
        json={
            "order_ids": [ok_order, ng_order, 999999],
            "cancel_reason_code": "stale_delivery",
            "note": "bulk cancel",
        },
    )
    assert res.status_code == 200
    assert res.json()["total"] == 3
    assert res.json()["succeeded"] == 1
    assert res.json()["failed"] == 2
    codes = {e["code"] for e in res.json()["errors"]}
    assert "ORDER_CANCEL_CONFLICT" in codes
    assert "ORDER_NOT_FOUND" in codes

    detail = client.get(f"/api/v1/orders/{ok_order}")
    assert detail.status_code == 200
    assert detail.json()["status"] == "cancelled"


def test_order_item_labels_pdf_single_and_multi_and_size():
    client = _client()
    i1 = _seed_order_item_for_label(customer_name="取引先A", product_name="日本語商品", note="備考メモ")
    i2 = _seed_order_item_for_label(customer_name="客戶B", product_name="中文商品", note="備註")

    single = client.post("/api/v1/orders/item-labels/pdf", json={"order_item_ids": [i1]})
    assert single.status_code == 200
    assert single.headers["content-type"].startswith("application/pdf")
    body = single.content
    assert b"%PDF-1." in body
    assert b"/MediaBox [ 0 0 255.12 368.5 ]" in body or b"/MediaBox [0 0 255.12 368.5]" in body or b"/MediaBox [0 0 255.12 368.50]" in body

    multi = client.post("/api/v1/orders/item-labels/pdf", json={"order_item_ids": [i2, i1]})
    assert multi.status_code == 200
    assert b"/Type /Page" in multi.content


def test_order_item_labels_pdf_includes_customer_region_in_payload(monkeypatch):
    captured = {}

    from app.api import routes_orders as ro

    def fake_build_label_pdf(pages):
        captured["pages"] = pages
        return b"%PDF-1.4\n%mock\n"

    monkeypatch.setattr(ro, "_build_label_pdf", fake_build_label_pdf)

    client = _client()
    item_id = _seed_order_item_for_label()

    res = client.post("/api/v1/orders/item-labels/pdf", json={"order_item_ids": [item_id]})
    assert res.status_code == 200

    pages = captured.get("pages")
    assert pages is not None and len(pages) == 1
    assert pages[0]["region"] == "HK"


def test_purchase_confirmation_pdf_sort_and_404():
    client = _client()
    item_id = _seed_order_item_for_label()

    ok = client.post("/api/v1/reports/purchase-confirmation/pdf", json={"selected_ids": [item_id]})
    assert ok.status_code == 200
    assert ok.headers["content-type"].startswith("application/pdf")

    nf = client.post("/api/v1/reports/purchase-confirmation/pdf", json={"selected_ids": [999999]})
    assert nf.status_code == 404


def test_purchase_confirmation_pdf_zero_selection_is_422():
    client = _client()
    bad = client.post("/api/v1/reports/purchase-confirmation/pdf", json={"selected_ids": []})
    assert bad.status_code == 422


def test_order_item_labels_pdf_404_and_422():
    client = _client()
    nf = client.post("/api/v1/orders/item-labels/pdf", json={"order_item_ids": [999999]})
    assert nf.status_code == 404

    bad = client.post("/api/v1/orders/item-labels/pdf", json={"order_item_ids": []})
    assert bad.status_code == 422


def test_bulk_cancel_orders_all_failed_returns_409():
    client = _client()
    d = date.today()
    ng_order = _seed_order_with_status_and_delivery(OrderStatus.shipped, d)

    res = client.post(
        "/api/v1/orders/bulk-cancel",
        json={
            "order_ids": [ng_order, 999999],
            "cancel_reason_code": "stale_delivery",
            "note": "bulk cancel",
        },
    )
    assert res.status_code == 409
    assert res.json()["detail"]["code"] == "ORDER_BULK_CANCEL_CONFLICT"
    assert isinstance(res.json()["detail"]["details"], list)


def test_bulk_cancel_orders_invalid_reason_code_is_422():
    client = _client()
    d = date.today()
    ok_order = _seed_order_with_status_and_delivery(OrderStatus.confirmed, d)

    res = client.post(
        "/api/v1/orders/bulk-cancel",
        json={
            "order_ids": [ok_order],
            "cancel_reason_code": "stale_cleanup",
        },
    )
    assert res.status_code == 422
