from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.entities import (
    AuditLog,
    Customer,
    Invoice,
    InvoiceNumberSequence,
    InvoiceItem,
    InvoiceStatus,
    LineStatus,
    Order,
    OrderItem,
    OrderStatus,
    PricingBasis,
    Product,
    PurchaseResult,
    PurchaseResultStatus,
    SupplierAllocation,
    SystemSettings,
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


def _seed_system_settings(
    *,
    exchange_rate: str = "1.0000",
    jp_gross_margin_pct: str | None = "25.000",
    jp_gross_margin_rate: str | None = None,
    hk_gross_margin_pct: str = "25.000",
    freight_unit_price: str = "0.00",
) -> None:
    db = TestingSessionLocal()
    normalized_margin = jp_gross_margin_rate if jp_gross_margin_rate is not None else jp_gross_margin_pct
    assert normalized_margin is not None
    row = db.query(SystemSettings).filter(SystemSettings.id == 1).first()
    if row is None:
        row = SystemSettings(
            id=1,
            exchange_rate=Decimal(exchange_rate),
            jp_gross_margin_pct=Decimal(normalized_margin),
            hk_gross_margin_pct=Decimal(hk_gross_margin_pct),
            freight_unit_price=Decimal(freight_unit_price),
        )
        db.add(row)
    else:
        row.exchange_rate = Decimal(exchange_rate)
        row.jp_gross_margin_pct = Decimal(normalized_margin)
        row.hk_gross_margin_pct = Decimal(hk_gross_margin_pct)
        row.freight_unit_price = Decimal(freight_unit_price)
    db.commit()
    db.close()


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
            freight_weight=Decimal("0.500"),
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


def _seed_purchase_result_for_order(order_id: int, purchased_qty: float = 2, unit_cost: float | None = None, final_unit_cost: float | None = None) -> int:
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
        unit_cost=unit_cost,
        final_unit_cost=final_unit_cost,
        result_status=PurchaseResultStatus.filled,
        invoiceable_flag=True,
    )
    db.add(pr)
    db.commit()
    rid = pr.id
    db.close()
    return rid


def _add_extra_order_items(order_id: int, count: int) -> None:
    db = TestingSessionLocal()
    for idx in range(count):
        product = Product(
            sku=f"SKU-INV-PDF-{datetime.now(UTC).timestamp()}-{idx}",
            name=f"Invoice PDF Product {idx}",
            order_uom="count",
            purchase_uom="count",
            invoice_uom="count",
            is_catch_weight=False,
            weight_capture_required=False,
            pricing_basis_default=PricingBasis.uom_count,
            active=True,
        )
        db.add(product)
        db.flush()
        db.add(
            OrderItem(
                order_id=order_id,
                product_id=product.id,
                ordered_qty=idx + 1,
                pricing_basis=PricingBasis.uom_count,
                unit_price_uom_count=100 + idx,
                unit_price_uom_kg=None,
            )
        )
    db.commit()
    db.close()


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
    assert created.json()["uuid"]
    assert created.json()["invoice_draft_no"].startswith("IVD-")
    assert created.json()["official_invoice_no"] is None
    assert created.json()["invoice_no"] == created.json()["invoice_draft_no"]

    got = client.get(f"/api/v1/invoices/{invoice_id}")
    assert got.status_code == 200
    assert got.json()["id"] == invoice_id
    assert got.json()["uuid"] == created.json()["uuid"]

    got_by_uuid = client.get(f"/api/v1/invoices/uuid/{created.json()['uuid']}")
    assert got_by_uuid.status_code == 200
    assert got_by_uuid.json()["id"] == invoice_id

    fin = client.post(f"/api/v1/invoices/{invoice_id}/finalize")
    assert fin.status_code == 200
    assert fin.json()["status"] == "finalized"
    assert fin.json()["is_locked"] is True
    assert fin.json()["official_invoice_no"].startswith(f"INV/{date.today().year}/")
    assert fin.json()["invoice_no"] == fin.json()["official_invoice_no"]

    report_by_uuid = client.get(f"/api/v1/invoices/uuid/{created.json()['uuid']}/report")
    assert report_by_uuid.status_code == 200
    assert report_by_uuid.json()["invoice_id"] == invoice_id
    assert report_by_uuid.json()["delivery_no"].startswith("DLV-")

    db = TestingSessionLocal()
    order = db.query(Order).filter(Order.id == order_id).first()
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    lines = db.query(OrderItem).filter(OrderItem.order_id == order_id).order_by(OrderItem.created_at.asc()).all()
    assert order is not None
    assert invoice is not None
    assert order.status == OrderStatus.invoiced
    assert order.delivery_no is not None
    assert order.delivery_no.startswith("DLV-")
    assert invoice.delivery_no == order.delivery_no
    assert all(line.line_status == LineStatus.invoiced for line in lines)
    db.close()

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

    db = TestingSessionLocal()
    order = db.query(Order).filter(Order.id == order_id).first()
    lines = db.query(OrderItem).filter(OrderItem.order_id == order_id).order_by(OrderItem.id.asc()).all()
    assert order is not None
    assert order.status == OrderStatus.shipped
    assert all(line.line_status == LineStatus.shipped for line in lines)
    db.close()


def test_finalize_invoice_allocates_official_number_from_year_sequence():
    client = _client()
    invoice_date = date(2099, 4, 1)

    first = client.post(
        "/api/v1/invoices/generate",
        json={"invoice_no": "INV-SEQ-1", "order_id": _seed_order(with_items=True), "invoice_date": str(invoice_date)},
    )
    assert first.status_code == 201
    second = client.post(
        "/api/v1/invoices/generate",
        json={"invoice_no": "INV-SEQ-2", "order_id": _seed_order(with_items=True), "invoice_date": str(invoice_date)},
    )
    assert second.status_code == 201

    first_fin = client.post(f"/api/v1/invoices/{first.json()['id']}/finalize")
    second_fin = client.post(f"/api/v1/invoices/{second.json()['id']}/finalize")
    assert first_fin.status_code == 200
    assert second_fin.status_code == 200
    assert first_fin.json()["official_invoice_no"] == "INV/2099/00001"
    assert second_fin.json()["official_invoice_no"] == "INV/2099/00002"

    db = TestingSessionLocal()
    seq = db.query(InvoiceNumberSequence).filter(InvoiceNumberSequence.year == 2099).first()
    assert seq is not None
    assert seq.next_seq == 3
    db.close()


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
    assert body["uuid"]
    assert body["delivery_no"] is None
    assert body["invoice_draft_no"].startswith("IVD-")
    assert body["invoice_no"] == body["invoice_draft_no"]
    assert body["official_invoice_no"] is None
    assert float(body["subtotal"]) == 1850.0
    assert float(body["grand_total"]) == 1850.0

    db = TestingSessionLocal()
    invoice_items = db.query(InvoiceItem).filter(InvoiceItem.invoice_id == body["id"]).all()
    order_lines = db.query(OrderItem).filter(OrderItem.order_id == order_id).order_by(OrderItem.id.asc()).all()
    db.close()
    assert len(invoice_items) == 2
    assert all(item.invoice_line_no is not None for item in invoice_items)
    assert all(line.line_status != LineStatus.invoiced for line in order_lines)

    items_by_uuid = client.get(f"/api/v1/invoices/uuid/{body['uuid']}/items")
    assert items_by_uuid.status_code == 200
    assert len(items_by_uuid.json()) == 2


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


def test_finalize_batch_invoices_partial_success():
    client = _client()
    order_id_ok = _seed_order(with_items=True)
    order_id_locked = _seed_order(with_items=True)
    order_id_empty = _seed_order(with_items=False)

    ok = client.post(
        "/api/v1/invoices/generate",
        json={"invoice_no": "INV-BATCH-OK-1", "order_id": order_id_ok, "invoice_date": str(date.today())},
    )
    assert ok.status_code == 201
    ok_id = ok.json()["id"]

    locked = client.post(
        "/api/v1/invoices/generate",
        json={"invoice_no": "INV-BATCH-LOCK-1", "order_id": order_id_locked, "invoice_date": str(date.today())},
    )
    assert locked.status_code == 201
    locked_id = locked.json()["id"]
    locked_fin = client.post(f"/api/v1/invoices/{locked_id}/finalize")
    assert locked_fin.status_code == 200

    empty = client.post(
        "/api/v1/invoices",
        json={"invoice_no": "INV-BATCH-EMPTY-1", "order_id": order_id_empty, "invoice_date": str(date.today())},
    )
    assert empty.status_code == 201
    empty_id = empty.json()["id"]

    batch = client.post(
        "/api/v1/invoices/finalize-batch",
        json={"invoice_ids": [ok_id, locked_id, empty_id, 999999, ok_id]},
    )
    assert batch.status_code == 200
    body = batch.json()
    assert body["success_count"] == 1
    assert body["failure_count"] == 3
    assert len(body["results"]) == 4

    result_by_id = {row["invoice_id"]: row for row in body["results"]}
    assert result_by_id[ok_id]["ok"] is True
    assert result_by_id[ok_id]["status"] == "finalized"
    assert result_by_id[ok_id]["is_locked"] is True
    assert result_by_id[locked_id]["ok"] is False
    assert result_by_id[locked_id]["reason_code"] == "INVOICE_NOT_DRAFT"
    assert result_by_id[empty_id]["ok"] is False
    assert result_by_id[empty_id]["reason_code"] == "INVOICE_ITEMS_REQUIRED"
    assert result_by_id[999999]["ok"] is False
    assert result_by_id[999999]["reason_code"] == "INVOICE_NOT_FOUND"

    db = TestingSessionLocal()
    ok_row = db.query(Invoice).filter(Invoice.id == ok_id).first()
    locked_row = db.query(Invoice).filter(Invoice.id == locked_id).first()
    empty_row = db.query(Invoice).filter(Invoice.id == empty_id).first()
    ok_order = db.query(Order).filter(Order.id == order_id_ok).first()
    locked_order = db.query(Order).filter(Order.id == order_id_locked).first()
    db.close()
    assert ok_row is not None and ok_row.status == InvoiceStatus.finalized and ok_row.is_locked is True
    assert locked_row is not None and locked_row.status == InvoiceStatus.finalized and locked_row.is_locked is True
    assert empty_row is not None and empty_row.status == InvoiceStatus.draft and empty_row.is_locked is False
    assert ok_order is not None and ok_order.status == OrderStatus.invoiced
    assert locked_order is not None and locked_order.status == OrderStatus.invoiced


def test_finalize_batch_writes_finalize_audit_logs():
    client = _client()
    order_id = _seed_order(with_items=True)

    created = client.post(
        "/api/v1/invoices/generate",
        json={"invoice_no": "INV-BATCH-AUD-1", "order_id": order_id, "invoice_date": str(date.today())},
    )
    assert created.status_code == 201
    invoice_id = created.json()["id"]

    batch = client.post("/api/v1/invoices/finalize-batch", json={"invoice_ids": [invoice_id]})
    assert batch.status_code == 200
    assert batch.json()["success_count"] == 1

    db = TestingSessionLocal()
    logs = db.query(AuditLog).filter(AuditLog.entity_type == "invoice", AuditLog.entity_id == invoice_id).all()
    db.close()
    assert any(log.action == "finalize" and log.reason_code == "batch_finalize" for log in logs)


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


def test_get_invoice_pdf_success_and_not_found():
    order_id = _seed_order(with_items=True)
    client = _client()

    gen = client.post(
        "/api/v1/invoices/generate",
        json={"invoice_no": "INV-PDF-001", "order_id": order_id, "invoice_date": str(date.today()), "due_date": str(date.today())},
    )
    assert gen.status_code == 201
    invoice_id = gen.json()["id"]

    pdf_res = client.get(f"/api/v1/invoices/{invoice_id}/pdf")
    assert pdf_res.status_code == 200
    assert pdf_res.headers["content-type"].startswith("application/pdf")
    assert f'{gen.json()["invoice_no"]}.pdf' in pdf_res.headers.get("content-disposition", "")
    assert len(pdf_res.content) > 1000

    nf = client.get("/api/v1/invoices/999999/pdf")
    assert nf.status_code == 404
    assert nf.json()["detail"]["code"] == "INVOICE_NOT_FOUND"


def test_get_invoice_pdf_without_items_is_409():
    order_id = _seed_order(with_items=False)
    client = _client()
    created = client.post(
        "/api/v1/invoices",
        json={"invoice_no": "INV-PDF-NOITEM", "order_id": order_id, "invoice_date": str(date.today())},
    )
    assert created.status_code == 201

    res = client.get(f"/api/v1/invoices/{created.json()['id']}/pdf")
    assert res.status_code == 409
    assert res.json()["detail"]["code"] == "INVOICE_ITEMS_REQUIRED"


def test_get_invoice_pdf_multi_page():
    order_id = _seed_order(with_items=True)
    _add_extra_order_items(order_id, 40)
    client = _client()
    gen = client.post(
        "/api/v1/invoices/generate",
        json={"invoice_no": "INV-PDF-MULTI", "order_id": order_id, "invoice_date": str(date.today())},
    )
    assert gen.status_code == 201

    pdf_res = client.get(f"/api/v1/invoices/{gen.json()['id']}/pdf")
    assert pdf_res.status_code == 200
    assert pdf_res.headers["content-type"].startswith("application/pdf")
    assert pdf_res.content.count(b"/Type /Page") >= 2


def test_generate_draft_from_purchase_results_and_finalize_separation():
    order_id = _seed_order(with_items=True)
    _seed_system_settings()
    purchase_result_id = _seed_purchase_result_for_order(order_id, purchased_qty=2, final_unit_cost=1000)
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
    # (1000/20 + 50) / 0.75 = 133.333... => 133.33
    assert float(items.json()[0]["sales_unit_price"]) == 133.33
    assert float(items.json()[0]["unit_cost_basis"]) == 40.0
    assert float(items.json()[0]["gross_margin_pct"]) == 70.0
    assert items.json()[0]["gross_margin_unavailable"] is False
    assert float(items.json()[0]["tax_amount"]) == 0.0

    fin = client.post(f"/api/v1/invoices/{invoice_id}/finalize")
    assert fin.status_code == 200
    assert fin.json()["status"] == "finalized"

    db = TestingSessionLocal()
    order = db.query(Order).filter(Order.id == order_id).first()
    lines = db.query(OrderItem).filter(OrderItem.order_id == order_id).all()
    assert order is not None
    assert order.status == OrderStatus.shipped
    assert sum(1 for line in lines if line.line_status == LineStatus.invoiced) == 1
    assert sum(1 for line in lines if line.line_status != LineStatus.invoiced) == 1
    db.close()


def test_draft_generation_price_auto_calc_missing_cost_sets_zero_and_error():
    order_id = _seed_order(with_items=True)
    _seed_system_settings()
    purchase_result_id = _seed_purchase_result_for_order(order_id, purchased_qty=2)
    client = _client()

    draft = client.post(
        "/api/v1/invoices/generate-draft-from-purchase-results",
        json={
            "invoice_no": "INV-PR-AUTO-MISS-001",
            "order_id": order_id,
            "invoice_date": str(date.today()),
            "purchase_result_ids": [purchase_result_id],
        },
    )
    assert draft.status_code == 201
    invoice_id = draft.json()["invoice_id"]

    items = client.get(f"/api/v1/invoices/{invoice_id}/items")
    assert items.status_code == 200
    assert float(items.json()[0]["sales_unit_price"]) == 0.0
    assert items.json()[0]["auto_price_error"] is not None


def test_invoice_draft_list_margin_formula_and_edge_cases():
    order_id = _seed_order(with_items=True)
    _seed_system_settings()
    purchase_result_id = _seed_purchase_result_for_order(order_id, purchased_qty=2, final_unit_cost=1000)
    client = _client()

    draft = client.post(
        "/api/v1/invoices/generate-draft-from-purchase-results",
        json={
            "invoice_no": "INV-PR-MARGIN-001",
            "order_id": order_id,
            "invoice_date": str(date.today()),
            "purchase_result_ids": [purchase_result_id],
        },
    )
    assert draft.status_code == 201

    invoice_id = draft.json()["invoice_id"]

    listed = client.get("/api/v1/invoices/draft-list")
    assert listed.status_code == 200
    row = next(r for r in listed.json() if r["invoice_id"] == invoice_id)

    # HKD cost = 1000 / 25 / 1 + 0 = 40.00
    # margin = (133.33 - 40.00) / 133.33 * 100 => 70.00%
    assert float(row["unit_cost_basis"]) == 40.0
    assert row["gross_margin_pct"] is not None
    assert float(row["gross_margin_pct"]) == 70.0
    assert row["gross_margin_unavailable"] is False

    # 請求単価=0 は計算不可
    invoice_item_id = row["invoice_item_id"]
    patched = client.patch(
        f"/api/v1/invoices/{invoice_id}/items/{invoice_item_id}",
        json={"billable_qty": row["billable_qty"], "sales_unit_price": 0},
    )
    assert patched.status_code == 200

    listed2 = client.get("/api/v1/invoices/draft-list")
    row2 = listed2.json()[0]
    assert row2["gross_margin_pct"] is None
    assert row2["gross_margin_unavailable"] is True


def test_invoice_draft_list_rows_include_required_columns():
    order_id = _seed_order(with_items=True)
    _seed_system_settings()
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
        "invoice_uuid",
        "invoice_item_uuid",
        "tracking_no",
        "invoice_no",
        "invoice_draft_no",
        "official_invoice_no",
        "invoice_line_no",
        "invoice_date",
        "delivery_date",
        "status",
        "customer_name",
        "product_name",
        "billable_qty",
        "billable_uom",
        "sales_unit_price",
        "line_amount",
        "gross_margin_pct",
        "gross_margin_unavailable",
    }.issubset(row.keys())
    assert row["invoice_draft_no"].startswith("IVD-")
    assert row["invoice_uuid"]
    assert row["invoice_item_uuid"]
    assert row["invoice_no"] == row["invoice_draft_no"]
    assert row["status"] == "draft"


def test_draft_generation_uses_system_settings_and_freight_weight():
    order_id = _seed_order(with_items=True)
    _seed_system_settings(exchange_rate="2.0000", jp_gross_margin_pct="25.000", freight_unit_price="12.00")
    purchase_result_id = _seed_purchase_result_for_order(order_id, purchased_qty=2, final_unit_cost=1000)
    client = _client()

    draft = client.post(
        "/api/v1/invoices/generate-draft-from-purchase-results",
        json={
            "invoice_no": "INV-PR-HKD-001",
            "order_id": order_id,
            "invoice_date": str(date.today()),
            "purchase_result_ids": [purchase_result_id],
        },
    )
    assert draft.status_code == 201

    items = client.get(f"/api/v1/invoices/{draft.json()['invoice_id']}/items")
    row = items.json()[0]
    # 1000 / 25 / 2 = 20.00, freight = 12 * 0.5 * 0.5 = 3.00, total = 23.00
    assert float(row["unit_cost_basis"]) == 23.0
    assert float(row["gross_margin_pct"]) == 82.75


def test_draft_generation_without_freight_weight_uses_zero_freight_component():
    order_id = _seed_order(with_items=True)
    _seed_system_settings(exchange_rate="2.0000", jp_gross_margin_pct="25.000", freight_unit_price="12.00")
    db = TestingSessionLocal()
    product = db.query(Product).filter(Product.name == "Count product").order_by(Product.id.desc()).first()
    assert product is not None
    product.freight_weight = None
    db.commit()
    db.close()
    purchase_result_id = _seed_purchase_result_for_order(order_id, purchased_qty=2, final_unit_cost=1000)
    client = _client()

    draft = client.post(
        "/api/v1/invoices/generate-draft-from-purchase-results",
        json={
            "invoice_no": "INV-PR-HKD-002",
            "order_id": order_id,
            "invoice_date": str(date.today()),
            "purchase_result_ids": [purchase_result_id],
        },
    )
    assert draft.status_code == 201

    items = client.get(f"/api/v1/invoices/{draft.json()['invoice_id']}/items")
    assert float(items.json()[0]["unit_cost_basis"]) == 20.0


def test_draft_generation_rounds_hkd_cost_and_margin_half_up():
    order_id = _seed_order(with_items=True)
    _seed_system_settings(exchange_rate="2.0000", jp_gross_margin_pct="25.000", freight_unit_price="10.00")
    db = TestingSessionLocal()
    product = db.query(Product).filter(Product.name == "Count product").order_by(Product.id.desc()).first()
    assert product is not None
    product.freight_weight = Decimal("0.333")
    db.commit()
    db.close()
    purchase_result_id = _seed_purchase_result_for_order(order_id, purchased_qty=2, final_unit_cost=1000)
    client = _client()

    draft = client.post(
        "/api/v1/invoices/generate-draft-from-purchase-results",
        json={
            "invoice_no": "INV-PR-HKD-003",
            "order_id": order_id,
            "invoice_date": str(date.today()),
            "purchase_result_ids": [purchase_result_id],
        },
    )
    assert draft.status_code == 201

    items = client.get(f"/api/v1/invoices/{draft.json()['invoice_id']}/items")
    row = items.json()[0]
    # 20 + (10 * 0.333 * 0.333 = 1.10889) => 21.11 after half-up rounding
    assert float(row["unit_cost_basis"]) == 21.11
    assert float(row["gross_margin_pct"]) == 84.17


def test_recalculate_draft_costs_reuses_current_settings_and_product_weight():
    order_id = _seed_order(with_items=True)
    _seed_system_settings(exchange_rate="2.0000", jp_gross_margin_pct="25.000", freight_unit_price="12.00")
    purchase_result_id = _seed_purchase_result_for_order(order_id, purchased_qty=2, final_unit_cost=1000)
    client = _client()

    draft = client.post(
        "/api/v1/invoices/generate-draft-from-purchase-results",
        json={
            "invoice_no": "INV-PR-RECALC-001",
            "order_id": order_id,
            "invoice_date": str(date.today()),
            "purchase_result_ids": [purchase_result_id],
        },
    )
    assert draft.status_code == 201
    invoice_id = draft.json()["invoice_id"]

    _seed_system_settings(exchange_rate="4.0000", jp_gross_margin_rate="20.000", freight_unit_price="8.00")
    db = TestingSessionLocal()
    product = db.query(Product).filter(Product.name == "Count product").order_by(Product.id.desc()).first()
    assert product is not None
    product.freight_weight = Decimal("1.000")
    db.commit()
    db.close()

    recalc = client.post(f"/api/v1/invoices/{invoice_id}/recalculate-draft-costs")
    assert recalc.status_code == 200
    assert recalc.json()["recalculated_count"] == 1

    items = client.get(f"/api/v1/invoices/{invoice_id}/items")
    row = items.json()[0]
    # 1000 / 20 / 4 = 12.50, freight = 8 * 1 * 1 = 8.00 => 20.50
    assert float(row["unit_cost_basis"]) == 20.5
    assert float(row["gross_margin_pct"]) == 84.62


def test_recalculate_draft_costs_rejects_non_draft_invoice():
    order_id = _seed_order(with_items=True)
    _seed_system_settings()
    purchase_result_id = _seed_purchase_result_for_order(order_id, purchased_qty=2, final_unit_cost=1000)
    client = _client()

    draft = client.post(
        "/api/v1/invoices/generate-draft-from-purchase-results",
        json={
            "invoice_no": "INV-PR-RECALC-002",
            "order_id": order_id,
            "invoice_date": str(date.today()),
            "purchase_result_ids": [purchase_result_id],
        },
    )
    invoice_id = draft.json()["invoice_id"]
    fin = client.post(f"/api/v1/invoices/{invoice_id}/finalize")
    assert fin.status_code == 200

    recalc = client.post(f"/api/v1/invoices/{invoice_id}/recalculate-draft-costs")
    assert recalc.status_code == 409
    assert recalc.json()["detail"]["code"] == "INVOICE_NOT_DRAFT"


def test_draft_generation_from_purchase_results_is_idempotent():
    order_id = _seed_order(with_items=True)
    _seed_system_settings()
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
    assert float(patch.json()["tax_amount"]) == 0.0

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


def test_finalize_and_reset_write_order_audit_logs():
    order_id = _seed_order(with_items=True)
    client = _client()

    gen = client.post(
        "/api/v1/invoices/generate",
        json={"invoice_no": "INV-AUD-ORDER-1", "order_id": order_id, "invoice_date": str(date.today())},
    )
    assert gen.status_code == 201
    invoice_id = gen.json()["id"]

    fin = client.post(f"/api/v1/invoices/{invoice_id}/finalize")
    assert fin.status_code == 200
    reset = client.post(
        f"/api/v1/invoices/{invoice_id}/reset-to-draft",
        json={"reset_reason_code": "data_error", "reason_note": "redo"},
    )
    assert reset.status_code == 200

    db = TestingSessionLocal()
    order_logs = db.query(AuditLog).filter(AuditLog.entity_type == "order", AuditLog.entity_id == order_id).all()
    order_item_logs = db.query(AuditLog).filter(AuditLog.entity_type == "order_item").all()
    db.close()
    assert len(order_logs) >= 2
    assert len(order_item_logs) >= 2


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

    # 一覧全体に既存データが混在しても、今回作成した3件の相対順は維持される
    created_positions = [listed_ids.index(invoice_id) for invoice_id in created_ids]
    assert created_positions[2] < created_positions[1] < created_positions[0]

    newest_created_id = created_ids[2]
    middle_created_id = created_ids[1]
    oldest_created_id = created_ids[0]

    head = client.get(f"/api/v1/invoices/{newest_created_id}/neighbors")
    assert head.status_code == 200
    # 新規3件のうち先頭なので、nextは中間を指す
    assert head.json()["next_invoice_id"] == middle_created_id

    middle = client.get(f"/api/v1/invoices/{middle_created_id}/neighbors")
    assert middle.status_code == 200
    assert middle.json()["prev_invoice_id"] == newest_created_id
    assert middle.json()["next_invoice_id"] == oldest_created_id

    tail = client.get(f"/api/v1/invoices/{oldest_created_id}/neighbors")
    assert tail.status_code == 200
    assert tail.json()["prev_invoice_id"] == middle_created_id


def test_invoice_neighbors_top_and_bottom_boundaries():
    client = _client()
    listed = client.get("/api/v1/invoices")
    assert listed.status_code == 200
    rows = listed.json()
    assert len(rows) >= 1

    top_id = rows[0]["id"]
    top_neighbors = client.get(f"/api/v1/invoices/{top_id}/neighbors")
    assert top_neighbors.status_code == 200
    assert top_neighbors.json()["prev_invoice_id"] is None

    bottom_id = rows[-1]["id"]
    bottom_neighbors = client.get(f"/api/v1/invoices/{bottom_id}/neighbors")
    assert bottom_neighbors.status_code == 200
    assert bottom_neighbors.json()["next_invoice_id"] is None


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
