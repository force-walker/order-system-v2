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
    InvoiceItem,
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
    _seed_purchase_result_for_order(order_id, purchased_qty=2)
    client = _client()

    draft = client.post(
        "/api/v1/invoices/generate-draft-from-purchase-results",
        json={
            "invoice_no": "INV-PR-DRAFT-001",
            "order_id": order_id,
            "invoice_date": str(date.today()),
        },
    )
    assert draft.status_code == 201
    invoice_id = draft.json()["id"]
    assert draft.json()["status"] == "draft"

    items = client.get(f"/api/v1/invoices/{invoice_id}/items")
    assert items.status_code == 200
    assert len(items.json()) >= 1

    fin = client.post(f"/api/v1/invoices/{invoice_id}/finalize")
    assert fin.status_code == 200
    assert fin.json()["status"] == "finalized"


def test_invoice_draft_list_rows_include_required_columns():
    order_id = _seed_order(with_items=True)
    _seed_purchase_result_for_order(order_id, purchased_qty=2)
    client = _client()

    draft = client.post(
        "/api/v1/invoices/generate-draft-from-purchase-results",
        json={
            "invoice_no": "INV-PR-LIST-001",
            "order_id": order_id,
            "invoice_date": str(date.today()),
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
