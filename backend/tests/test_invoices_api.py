from datetime import UTC, date, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.entities import (
    Customer,
    Invoice,
    InvoiceItem,
    InvoiceStatus,
    Order,
    OrderItem,
    OrderStatus,
    PricingBasis,
    Product,
    PurchaseResult,
    PurchaseResultStatus,
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


def _seed_order(with_items: bool = False, include_kg_without_weight: bool = False) -> int:
    db = TestingSessionLocal()
    c = Customer(customer_code=f"C-I-{datetime.now(UTC).timestamp()}", name="Customer I", active=True)
    db.add(c)
    db.flush()

    o = Order(
        order_no=f"ORD-I-{datetime.now(UTC).timestamp()}",
        customer_id=c.id,
        order_datetime=datetime.now(UTC),
        delivery_date=date.today(),
        status=OrderStatus.confirmed,
        note=None,
    )
    db.add(o)
    db.flush()

    if with_items:
        p_count = Product(
            sku=f"SKU-C-{datetime.now(UTC).timestamp()}",
            name="Count product",
            order_uom="count",
            purchase_uom="count",
            invoice_uom="count",
            tax_rate_code="10",
            is_catch_weight=False,
            weight_capture_required=False,
            pricing_basis_default=PricingBasis.uom_count,
            active=True,
        )
        db.add(p_count)
        db.flush()
        db.add(
            OrderItem(
                order_id=o.id,
                product_id=p_count.id,
                ordered_qty=3,
                pricing_basis=PricingBasis.uom_count,
                unit_price_uom_count=200,
                unit_price_uom_kg=None,
            )
        )

        p_kg = Product(
            sku=f"SKU-K-{datetime.now(UTC).timestamp()}",
            name="Kg product",
            order_uom="kg",
            purchase_uom="kg",
            invoice_uom="kg",
            is_catch_weight=True,
            weight_capture_required=True,
            pricing_basis_default=PricingBasis.uom_kg,
            active=True,
        )
        db.add(p_kg)
        db.flush()
        db.add(
            OrderItem(
                order_id=o.id,
                product_id=p_kg.id,
                ordered_qty=1,
                pricing_basis=PricingBasis.uom_kg,
                unit_price_uom_count=None,
                unit_price_uom_kg=1000,
                actual_weight_kg=(None if include_kg_without_weight else 1.25),
            )
        )

    db.commit()
    oid = o.id
    db.close()
    return oid


def _seed_purchase_result_for_order(order_id: int, purchased_qty: float = 2) -> int:
    db = TestingSessionLocal()
    item = db.query(OrderItem).filter(OrderItem.order_id == order_id).first()
    assert item is not None

    alloc = SupplierAllocation(
        order_item_id=item.id,
        suggested_supplier_id=101,
        suggested_qty=float(purchased_qty),
        final_supplier_id=101,
        final_qty=float(purchased_qty),
        final_uom="count",
    )
    db.add(alloc)
    db.flush()

    pr = PurchaseResult(
        allocation_id=alloc.id,
        supplier_id=101,
        purchased_qty=float(purchased_qty),
        purchased_uom="count",
        result_status=PurchaseResultStatus.filled,
        invoiceable_flag=True,
    )
    db.add(pr)
    db.commit()
    rid = pr.id
    db.close()
    return rid


def test_create_invoice_invalid_date_range_is_422():
    order_id = _seed_order()
    client = _client()

    today = date.today()
    bad = client.post(
        "/api/v1/invoices",
        json={
            "invoice_no": "INV-BAD-DATE",
            "order_id": order_id,
            "invoice_date": str(today),
            "due_date": str(today - timedelta(days=1)),
        },
    )
    assert bad.status_code == 422
    assert bad.json()["detail"]["code"] == "INVALID_DATE_RANGE"


def test_create_finalize_unlock_reset_invoice_flow():
    order_id = _seed_order(with_items=True)
    client = _client()

    created = client.post(
        "/api/v1/invoices/generate",
        json={"invoice_no": "INV-001", "order_id": order_id, "invoice_date": str(date.today())},
    )
    assert created.status_code == 201
    invoice_id = created.json()["id"]

    got = client.get(f"/api/v1/invoices/{invoice_id}")
    assert got.status_code == 200
    assert got.json()["id"] == invoice_id

    fin = client.post(f"/api/v1/invoices/{invoice_id}/finalize")
    assert fin.status_code == 200
    assert fin.json()["status"] == "finalized"
    assert fin.json()["is_locked"] is True

    unlock = client.post(
        f"/api/v1/invoices/{invoice_id}/unlock",
        json={"unlock_reason_code": "data_fix", "reason_note": "fix"},
    )
    assert unlock.status_code == 200
    assert unlock.json()["is_locked"] is False

    fin2 = client.post(f"/api/v1/invoices/{invoice_id}/finalize")
    assert fin2.status_code == 409

    reset = client.post(
        f"/api/v1/invoices/{invoice_id}/reset-to-draft",
        json={"reset_reason_code": "data_error", "reason_note": "redo"},
    )
    assert reset.status_code == 200
    assert reset.json()["status"] == "draft"


def test_generate_invoice_from_order_items_success():
    order_id = _seed_order(with_items=True)
    client = _client()

    res = client.post(
        "/api/v1/invoices/generate",
        json={
            "invoice_no": "INV-GEN-001",
            "order_id": order_id,
            "invoice_date": str(date.today()),
        },
    )
    assert res.status_code == 201
    body = res.json()
    assert body["invoice_no"] == "INV-GEN-001"
    assert float(body["subtotal"]) == 1850.0
    assert float(body["grand_total"]) == 1850.0

    db = TestingSessionLocal()
    invoice_items = db.query(InvoiceItem).filter(InvoiceItem.invoice_id == body["id"]).all()
    db.close()
    assert len(invoice_items) == 2


def test_generate_invoice_without_items_is_422():
    order_id = _seed_order(with_items=False)
    client = _client()

    res = client.post(
        "/api/v1/invoices/generate",
        json={
            "invoice_no": "INV-GEN-NOITEM",
            "order_id": order_id,
            "invoice_date": str(date.today()),
        },
    )
    assert res.status_code == 422
    assert res.json()["detail"]["code"] == "ORDER_ITEMS_NOT_FOUND"


def test_generate_invoice_missing_actual_weight_is_422():
    order_id = _seed_order(with_items=True, include_kg_without_weight=True)
    client = _client()

    res = client.post(
        "/api/v1/invoices/generate",
        json={
            "invoice_no": "INV-GEN-WEIGHT",
            "order_id": order_id,
            "invoice_date": str(date.today()),
        },
    )
    assert res.status_code == 422
    assert res.json()["detail"]["code"] == "MISSING_ACTUAL_WEIGHT"


def test_finalize_invoice_without_items_is_409():
    order_id = _seed_order(with_items=False)
    client = _client()

    created = client.post(
        "/api/v1/invoices",
        json={"invoice_no": "INV-NO-ITEMS", "order_id": order_id, "invoice_date": str(date.today())},
    )
    assert created.status_code == 201

    fin = client.post(f"/api/v1/invoices/{created.json()['id']}/finalize")
    assert fin.status_code == 409
    assert fin.json()["detail"]["code"] == "INVOICE_ITEMS_REQUIRED"


def test_list_invoice_items_and_invoice_filters():
    order_id = _seed_order(with_items=True)
    client = _client()

    gen = client.post(
        "/api/v1/invoices/generate",
        json={"invoice_no": "INV-LIST-1", "order_id": order_id, "invoice_date": str(date.today())},
    )
    assert gen.status_code == 201
    invoice_id = gen.json()["id"]

    items = client.get(f"/api/v1/invoices/{invoice_id}/items")
    assert items.status_code == 200
    assert len(items.json()) == 2

    filtered_by_status = client.get("/api/v1/invoices?status=draft")
    assert filtered_by_status.status_code == 200
    assert any(row["id"] == invoice_id for row in filtered_by_status.json())

    filtered_by_order = client.get(f"/api/v1/invoices?order_id={order_id}")
    assert filtered_by_order.status_code == 200
    assert any(row["id"] == invoice_id for row in filtered_by_order.json())


def test_generate_draft_from_purchase_results_and_finalize_separation():
    order_id = _seed_order(with_items=True)
    purchase_result_id = _seed_purchase_result_for_order(order_id, purchased_qty=2)
    client = _client()

    draft = client.post(
        "/api/v1/invoices/generate-draft-from-purchase-results",
        json={
            "invoice_no": "INV-PR-DRAFT-001",
            "order_id": order_id,
            "invoice_date": str(date.today()),
            "purchase_result_ids": [purchase_result_id],
        },
    )
    assert draft.status_code == 201
    invoice_id = draft.json()["invoice_id"]
    assert draft.json()["created_count"] == 1
    assert draft.json()["target_purchase_result_ids"] == [purchase_result_id]

    items = client.get(f"/api/v1/invoices/{invoice_id}/items")
    assert items.status_code == 200
    assert len(items.json()) >= 1

    fin = client.post(f"/api/v1/invoices/{invoice_id}/finalize")
    assert fin.status_code == 200
    assert fin.json()["status"] == "finalized"


def test_invoice_draft_list_rows_include_required_columns():
    order_id = _seed_order(with_items=True)
    purchase_result_id = _seed_purchase_result_for_order(order_id, purchased_qty=2)
    client = _client()

    draft = client.post(
        "/api/v1/invoices/generate-draft-from-purchase-results",
        json={
            "invoice_no": "INV-PR-LIST-001",
            "order_id": order_id,
            "invoice_date": str(date.today()),
            "purchase_result_ids": [purchase_result_id],
        },
    )
    assert draft.status_code == 201

    listed = client.get("/api/v1/invoices/draft-list")
    assert listed.status_code == 200
    assert len(listed.json()) >= 1

    row = listed.json()[0]
    assert {
        "invoice_id",
        "invoice_item_id",
        "customer_name",
        "product_name",
        "billable_qty",
        "billable_uom",
        "sales_unit_price",
        "line_amount",
        "gross_margin_pct",
    }.issubset(row.keys())


def test_draft_generation_from_purchase_results_is_idempotent():
    order_id = _seed_order(with_items=True)
    purchase_result_id = _seed_purchase_result_for_order(order_id, purchased_qty=2)
    client = _client()

    first = client.post(
        "/api/v1/invoices/generate-draft-from-purchase-results",
        json={
            "invoice_no": "INV-PR-IDEMP-1",
            "order_id": order_id,
            "invoice_date": str(date.today()),
            "purchase_result_ids": [purchase_result_id],
        },
    )
    assert first.status_code == 201
    assert first.json()["created_count"] == 1

    second = client.post(
        "/api/v1/invoices/generate-draft-from-purchase-results",
        json={
            "invoice_no": "INV-PR-IDEMP-2",
            "order_id": order_id,
            "invoice_date": str(date.today()),
            "purchase_result_ids": [purchase_result_id],
        },
    )
    assert second.status_code == 409
    assert second.json()["detail"]["code"] == "DRAFT_ALREADY_GENERATED"


def test_update_invoice_draft_item_recalculates_and_finalized_rejects():
    order_id = _seed_order(with_items=True)
    client = _client()

    gen = client.post(
        "/api/v1/invoices/generate",
        json={"invoice_no": "INV-EDIT-001", "order_id": order_id, "invoice_date": str(date.today())},
    )
    assert gen.status_code == 201
    invoice_id = gen.json()["id"]

    items = client.get(f"/api/v1/invoices/{invoice_id}/items")
    invoice_item_id = items.json()[0]["id"]

    patch = client.patch(
        f"/api/v1/invoices/{invoice_id}/items/{invoice_item_id}",
        json={"billable_qty": 5, "sales_unit_price": 123.45},
    )
    assert patch.status_code == 200
    assert float(patch.json()["line_amount"]) == 617.25
    assert float(patch.json()["tax_amount"]) == 61.72

    report = client.get(f"/api/v1/invoices/{invoice_id}/report")
    assert report.status_code == 200
    assert report.json()["customer_name"] == "Customer I"
    assert any(line["invoice_item_id"] == invoice_item_id for line in report.json()["items"])

    fin = client.post(f"/api/v1/invoices/{invoice_id}/finalize")
    assert fin.status_code == 200

    patch_after_finalize = client.patch(
        f"/api/v1/invoices/{invoice_id}/items/{invoice_item_id}",
        json={"billable_qty": 6, "sales_unit_price": 120},
    )
    assert patch_after_finalize.status_code == 409
    assert patch_after_finalize.json()["detail"]["code"] == "INVOICE_NOT_DRAFT"


def test_update_invoice_draft_item_non_negative_validation():
    order_id = _seed_order(with_items=True)
    client = _client()

    gen = client.post(
        "/api/v1/invoices/generate",
        json={"invoice_no": "INV-EDIT-NEG-1", "order_id": order_id, "invoice_date": str(date.today())},
    )
    invoice_id = gen.json()["id"]
    item_id = client.get(f"/api/v1/invoices/{invoice_id}/items").json()[0]["id"]

    patch = client.patch(
        f"/api/v1/invoices/{invoice_id}/items/{item_id}",
        json={"billable_qty": -1, "sales_unit_price": 100},
    )
    assert patch.status_code == 422


def test_finalize_invoice_item_line_status_transition():
    order_id = _seed_order(with_items=True)
    client = _client()

    gen = client.post(
        "/api/v1/invoices/generate",
        json={"invoice_no": "INV-LINE-FIN-1", "order_id": order_id, "invoice_date": str(date.today())},
    )
    invoice_id = gen.json()["id"]
    item_id = client.get(f"/api/v1/invoices/{invoice_id}/items").json()[0]["id"]

    fin_line = client.post(f"/api/v1/invoices/{invoice_id}/items/{item_id}/finalize")
    assert fin_line.status_code == 200
    assert fin_line.json()["invoice_line_status"] == "invoiced"

    fin_again = client.post(f"/api/v1/invoices/{invoice_id}/items/{item_id}/finalize")
    assert fin_again.status_code == 409
    assert fin_again.json()["detail"]["code"] == "INVOICE_ITEM_ALREADY_INVOICED"

    client.post(f"/api/v1/invoices/{invoice_id}/finalize")
    fin_after_header = client.post(f"/api/v1/invoices/{invoice_id}/items/{item_id}/finalize")
    assert fin_after_header.status_code == 409
    assert fin_after_header.json()["detail"]["code"] == "INVOICE_NOT_DRAFT"


def test_invoice_report_not_found():
    client = _client()
    res = client.get("/api/v1/invoices/999999/report")
    assert res.status_code == 404


def test_invoice_neighbors_follow_invoice_list_order():
    order_id = _seed_order(with_items=False)
    client = _client()

    created_ids: list[int] = []
    for no in ["INV-NB-001", "INV-NB-002", "INV-NB-003"]:
        res = client.post(
            "/api/v1/invoices",
            json={"invoice_no": no, "order_id": order_id, "invoice_date": str(date.today())},
        )
        assert res.status_code == 201
        created_ids.append(res.json()["id"])

    listed = client.get("/api/v1/invoices")
    assert listed.status_code == 200
    listed_ids = [row["id"] for row in listed.json()]

    assert listed_ids[0] == created_ids[2]
    assert listed_ids[1] == created_ids[1]
    assert listed_ids[2] == created_ids[0]

    head = client.get(f"/api/v1/invoices/{listed_ids[0]}/neighbors")
    assert head.status_code == 200
    assert head.json()["prev_invoice_id"] is None
    assert head.json()["next_invoice_id"] == listed_ids[1]

    middle = client.get(f"/api/v1/invoices/{listed_ids[1]}/neighbors")
    assert middle.status_code == 200
    assert middle.json()["prev_invoice_id"] == listed_ids[0]
    assert middle.json()["next_invoice_id"] == listed_ids[2]

    tail = client.get(f"/api/v1/invoices/{listed_ids[2]}/neighbors")
    assert tail.status_code == 200
    assert tail.json()["prev_invoice_id"] == listed_ids[1]
    assert tail.json()["next_invoice_id"] is None


def test_finalize_locks_invoice_row_state():
    order_id = _seed_order(with_items=True)
    client = _client()

    gen = client.post(
        "/api/v1/invoices/generate",
        json={"invoice_no": "INV-LOCK-001", "order_id": order_id, "invoice_date": str(date.today())},
    )
    invoice_id = gen.json()["id"]

    fin = client.post(f"/api/v1/invoices/{invoice_id}/finalize")
    assert fin.status_code == 200

    db = TestingSessionLocal()
    row = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    db.close()
    assert row is not None
    assert row.status == InvoiceStatus.finalized
    assert row.is_locked is True
