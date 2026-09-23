import json
import re
from datetime import UTC, date, datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.allocation_completion import evaluate_order_allocation_completion, synchronize_confirmed_order_allocation_status
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.entities import AuditLog, Customer, LineStatus, Order, OrderItem, OrderStatus, PricingBasis, Product, Supplier, SupplierAllocation, SupplierProduct


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


def _seed_order_item(product_name: str = "P", customer_name: str = "C") -> tuple[str, int, int, str]:
    db = TestingSessionLocal()
    supplier = Supplier(supplier_code=f"SUP-{datetime.now(UTC).timestamp()}", name="S", active=True)
    db.add(supplier)
    db.flush()

    customer = Customer(customer_code=f"C-{datetime.now(UTC).timestamp()}", name=customer_name, active=True)
    db.add(customer)
    db.flush()

    product = Product(
        sku=f"SKU-{datetime.now(UTC).timestamp()}",
        name=product_name,
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

    order = Order(
        order_no=f"ORD-{datetime.now(UTC).timestamp()}",
        customer_id=customer.id,
        order_datetime=datetime.now(UTC),
        delivery_date=date.today(),
        status=OrderStatus.confirmed,
        note=None,
    )
    db.add(order)
    db.flush()

    item = OrderItem(
        order_id=order.id,
        product_id=product.id,
        ordered_qty=5,
        pricing_basis=PricingBasis.uom_count,
        unit_price_uom_count=100,
        unit_price_uom_kg=None,
    )
    db.add(item)
    db.flush()

    mapping = SupplierProduct(
        supplier_id=supplier.id,
        product_id=product.id,
        priority=1,
        is_preferred=True,
    )
    db.add(mapping)
    db.commit()
    return item.id, supplier.id, product.id, order.id


def _seed_order_with_items(
    item_count: int = 2,
    *,
    ordered_qty: float = 5,
    order_status: OrderStatus = OrderStatus.confirmed,
    order_uom: str = "count",
    purchase_uom: str = "count",
    invoice_uom: str = "count",
    is_catch_weight: bool = False,
) -> tuple[str, list[str], int]:
    db = TestingSessionLocal()
    marker = str(datetime.now(UTC).timestamp())
    supplier = Supplier(supplier_code=f"SUP-M-{marker}", name="Multi Supplier", active=True)
    customer = Customer(customer_code=f"C-M-{marker}", name="Multi Customer", active=True)
    product = Product(
        sku=f"SKU-M-{marker}",
        name="Multi Product",
        order_uom=order_uom,
        purchase_uom=purchase_uom,
        invoice_uom=invoice_uom,
        is_catch_weight=is_catch_weight,
        weight_capture_required=is_catch_weight,
        pricing_basis_default=PricingBasis.uom_count,
        active=True,
    )
    db.add_all([supplier, customer, product])
    db.flush()
    order = Order(
        order_no=f"ORD-M-{marker}",
        customer_id=customer.id,
        order_datetime=datetime.now(UTC),
        delivery_date=date.today(),
        status=order_status,
        note=None,
    )
    db.add(order)
    db.flush()
    items = []
    for _ in range(item_count):
        item = OrderItem(
            order_id=order.id,
            product_id=product.id,
            ordered_qty=ordered_qty,
            pricing_basis=PricingBasis.uom_count,
            unit_price_uom_count=100,
            unit_price_uom_kg=None,
        )
        db.add(item)
        db.flush()
        items.append(item.id)
    db.commit()
    result = (order.id, items, supplier.id)
    db.close()
    return result


def test_worklist_suggest_and_bulk_save_flow():
    order_item_id, supplier_id, _, _ = _seed_order_item()
    client = _client()

    worklist = client.get("/api/v1/order-item-allocations?unallocated_only=true")
    assert worklist.status_code == 200
    assert any(x["order_item_id"] == order_item_id for x in worklist.json())

    row = [x for x in worklist.json() if x["order_item_id"] == order_item_id][0]
    assert "allocated_supplier_id" in row
    assert "allocated_qty" in row
    assert "delivery_date" in row
    assert row["order_id"]
    assert row["order_status"] == "confirmed"
    assert row["customer_name"] == "C"
    assert re.match(r"^\d{4}-\d{2}-\d{2}$", row["delivery_date"]) is not None

    suggest = client.post("/api/v1/order-item-allocations/suggestions", json={"order_item_ids": [order_item_id]})
    assert suggest.status_code == 200
    assert suggest.json()[0]["suggested_supplier_id"] == supplier_id
    assert "mapping" in suggest.json()[0]["reason"]

    saved = client.post(
        "/api/v1/order-item-allocations/bulk-save",
        json={"items": [{"order_item_id": order_item_id, "supplier_id": supplier_id, "allocated_qty": 5}]},
    )
    assert saved.status_code == 200
    assert saved.json()["succeeded"] == 1
    assert saved.json()["failed"] == 0

    db = TestingSessionLocal()
    item = db.query(OrderItem).filter(OrderItem.id == order_item_id).first()
    order = db.query(Order).filter(Order.id == item.order_id).first()
    assert item is not None and order is not None
    assert item.shipped_date == order.delivery_date
    assert item.line_status == LineStatus.allocated
    assert order.status == OrderStatus.allocated
    db.close()


def test_bulk_save_partial_success_and_validation_conflict():
    ok_item_id, supplier_id, _, _ = _seed_order_item(product_name="OK")
    ng_item_id, _, _, _ = _seed_order_item(product_name="NG")
    client = _client()

    result = client.post(
        "/api/v1/order-item-allocations/bulk-save",
        json={
            "items": [
                {"order_item_id": ok_item_id, "supplier_id": supplier_id, "allocated_qty": 2},
                {"order_item_id": ng_item_id, "supplier_id": supplier_id, "allocated_qty": 999},
            ]
        },
    )
    assert result.status_code == 200
    assert result.json()["succeeded"] == 1
    assert result.json()["failed"] == 1
    assert result.json()["errors"][0]["code"] in {"ALLOCATED_QTY_EXCEEDS_ORDERED_QTY", "SUPPLIER_NOT_FOUND"}

    db = TestingSessionLocal()
    ok_item = db.query(OrderItem).filter(OrderItem.id == ok_item_id).first()
    ng_item = db.query(OrderItem).filter(OrderItem.id == ng_item_id).first()
    assert ok_item is not None and ng_item is not None
    assert ok_item.line_status == LineStatus.open
    assert ok_item.shipped_date is None
    assert ng_item.line_status != LineStatus.allocated
    assert ng_item.shipped_date is None
    db.close()

    bad = client.post(
        "/api/v1/order-item-allocations/bulk-save",
        json={"items": [{"order_item_id": ok_item_id, "supplier_id": supplier_id, "allocated_qty": 0}]},
    )
    assert bad.status_code == 422

    missing_qty = client.post(
        "/api/v1/order-item-allocations/bulk-save",
        json={"items": [{"order_item_id": ok_item_id, "supplier_id": supplier_id}]},
    )
    assert missing_qty.status_code == 200
    assert missing_qty.json()["failed"] == 1
    assert missing_qty.json()["errors"][0]["code"] == "ALLOCATED_QTY_REQUIRED"


def test_bulk_save_can_unassign_supplier_with_null_values():
    order_item_id, supplier_id, _, _ = _seed_order_item()
    client = _client()

    assigned = client.post(
        "/api/v1/order-item-allocations/bulk-save",
        json={"items": [{"order_item_id": order_item_id, "supplier_id": supplier_id, "allocated_qty": 3}]},
    )
    assert assigned.status_code == 200
    assert assigned.json()["succeeded"] == 1

    unassigned = client.post(
        "/api/v1/order-item-allocations/bulk-save",
        json={"items": [{"order_item_id": order_item_id, "supplier_id": None, "allocated_qty": None}]},
    )
    assert unassigned.status_code == 200
    assert unassigned.json()["succeeded"] == 1

    worklist = client.get("/api/v1/order-item-allocations")
    assert worklist.status_code == 200
    row = [x for x in worklist.json() if x["order_item_id"] == order_item_id][0]
    assert row["allocated_supplier_id"] is None
    assert row["allocated_qty"] is None

    bad_unassign = client.post(
        "/api/v1/order-item-allocations/bulk-save",
        json={"items": [{"order_item_id": order_item_id, "supplier_id": None, "allocated_qty": 1}]},
    )
    assert bad_unassign.status_code == 200
    assert bad_unassign.json()["failed"] == 1
    assert bad_unassign.json()["errors"][0]["code"] == "UNASSIGN_WITH_QTY_NOT_ALLOWED"


def test_worklist_filters_by_product_and_customer_with_paging():
    _seed_order_item(product_name="Apple", customer_name="Alpha")
    _seed_order_item(product_name="Banana", customer_name="Beta")
    client = _client()

    by_product = client.get("/api/v1/order-item-allocations?product_name=Apple")
    assert by_product.status_code == 200
    assert len(by_product.json()) >= 1
    assert all("Apple" in row["product_name"] for row in by_product.json())

    by_customer = client.get("/api/v1/order-item-allocations?customer_name=Beta")
    assert by_customer.status_code == 200
    assert len(by_customer.json()) >= 1

    by_none = client.get("/api/v1/order-item-allocations?product_name=Orange")
    assert by_none.status_code == 200
    assert by_none.json() == []

    all_rows = client.get("/api/v1/order-item-allocations")
    assert all_rows.status_code == 200
    assert len(all_rows.json()) >= 2

    paged = client.get("/api/v1/order-item-allocations?limit=1&offset=1")
    assert paged.status_code == 200
    assert len(paged.json()) == 1

    confirmed = client.get("/api/v1/order-item-allocations?order_status=confirmed&order_status=allocated")
    assert confirmed.status_code == 200
    assert len(confirmed.json()) >= 2
    assert all(row["order_status"] in {"confirmed", "allocated"} for row in confirmed.json())

    excluded = client.get("/api/v1/order-item-allocations?order_status=new")
    assert excluded.status_code == 200
    assert excluded.json() == []


def test_two_line_order_advances_only_after_whole_order_is_complete():
    order_id, item_ids, supplier_id = _seed_order_with_items()
    client = _client()

    first = client.post(
        "/api/v1/order-item-allocations/bulk-save",
        json={"items": [{"order_item_id": item_ids[0], "supplier_id": supplier_id, "allocated_qty": 5}]},
    )
    assert first.status_code == 200
    db = TestingSessionLocal()
    order = db.query(Order).filter(Order.id == order_id).one()
    items = db.query(OrderItem).filter(OrderItem.order_id == order_id).order_by(OrderItem.line_no).all()
    assert order.status == OrderStatus.confirmed
    assert [item.line_status for item in items] == [LineStatus.allocated, LineStatus.open]
    db.close()

    cleared = client.post(
        "/api/v1/order-item-allocations/bulk-save",
        json={"items": [{"order_item_id": item_ids[0], "supplier_id": None, "allocated_qty": None}]},
    )
    assert cleared.status_code == 200
    db = TestingSessionLocal()
    order = db.query(Order).filter(Order.id == order_id).one()
    items = db.query(OrderItem).filter(OrderItem.order_id == order_id).order_by(OrderItem.line_no).all()
    assert order.status == OrderStatus.confirmed
    assert [item.line_status for item in items] == [LineStatus.open, LineStatus.open]
    rollback_audit = (
        db.query(AuditLog)
        .filter(
            AuditLog.entity_type == "order_item",
            AuditLog.entity_id == item_ids[0],
            AuditLog.reason_code == "allocation_completion",
        )
        .order_by(AuditLog.id.desc())
        .first()
    )
    assert rollback_audit is not None
    assert json.loads(rollback_audit.before_json)["line_status"] == "allocated"
    assert json.loads(rollback_audit.after_json)["line_status"] == "open"
    db.close()

    restored = client.post(
        "/api/v1/order-item-allocations/bulk-save",
        json={"items": [{"order_item_id": item_ids[0], "supplier_id": supplier_id, "allocated_qty": 5}]},
    )
    assert restored.status_code == 200
    db = TestingSessionLocal()
    assert db.query(OrderItem).filter(OrderItem.id == item_ids[0]).one().line_status == LineStatus.allocated
    db.close()

    second = client.post(
        "/api/v1/order-item-allocations/bulk-save",
        json={"items": [{"order_item_id": item_ids[1], "supplier_id": supplier_id, "allocated_qty": 5}]},
    )
    assert second.status_code == 200
    db = TestingSessionLocal()
    order = db.query(Order).filter(Order.id == order_id).one()
    items = db.query(OrderItem).filter(OrderItem.order_id == order_id).all()
    assert order.status == OrderStatus.allocated
    assert all(item.line_status == LineStatus.allocated for item in items)
    db.close()


def test_cancelled_line_is_excluded_from_order_completion():
    order_id, item_ids, supplier_id = _seed_order_with_items()
    db = TestingSessionLocal()
    cancelled_item = db.query(OrderItem).filter(OrderItem.id == item_ids[1]).one()
    cancelled_item.line_status = LineStatus.cancelled
    db.commit()
    db.close()

    response = _client().post(
        "/api/v1/order-item-allocations/bulk-save",
        json={"items": [{"order_item_id": item_ids[0], "supplier_id": supplier_id, "allocated_qty": 5}]},
    )
    assert response.status_code == 200
    db = TestingSessionLocal()
    order = db.query(Order).filter(Order.id == order_id).one()
    active_item = db.query(OrderItem).filter(OrderItem.id == item_ids[0]).one()
    cancelled_item = db.query(OrderItem).filter(OrderItem.id == item_ids[1]).one()
    assert order.status == OrderStatus.allocated
    assert active_item.line_status == LineStatus.allocated
    assert cancelled_item.line_status == LineStatus.cancelled
    db.close()


def test_completion_reasons_cover_missing_supplier_invalid_qty_and_uom():
    order_id, item_ids, supplier_id = _seed_order_with_items(item_count=1)
    db = TestingSessionLocal()
    allocation = SupplierAllocation(order_item_id=item_ids[0], final_supplier_id=None, final_qty=5, final_uom="count")
    db.add(allocation)
    db.flush()
    result = evaluate_order_allocation_completion(db, order_id)
    assert result.complete is False
    assert "SUPPLIER_MISSING" in {reason.code for reason in result.reasons}

    allocation.final_supplier_id = supplier_id
    allocation.final_qty = 0
    result = evaluate_order_allocation_completion(db, order_id)
    assert result.complete is False
    assert "FINAL_QTY_INVALID" in {reason.code for reason in result.reasons}

    allocation.final_qty = 5
    allocation.final_uom = "kg"
    result = evaluate_order_allocation_completion(db, order_id)
    assert result.complete is False
    assert "FINAL_UOM_MISMATCH" in {reason.code for reason in result.reasons}
    db.rollback()
    db.close()


def test_completion_accepts_pc_and_ctn_when_order_and_purchase_uom_match():
    for uom in ("PC", "CTN"):
        order_id, item_ids, supplier_id = _seed_order_with_items(item_count=1, order_uom=uom, purchase_uom=uom)
        db = TestingSessionLocal()
        db.add(
            SupplierAllocation(
                order_item_id=item_ids[0],
                final_supplier_id=supplier_id,
                final_qty=5,
                final_uom=uom,
            )
        )
        db.flush()
        result = evaluate_order_allocation_completion(db, order_id)
        assert result.complete is True
        assert result.reasons == ()
        db.rollback()
        db.close()


def test_catch_weight_allocation_uses_ctn_and_ignores_actual_weight():
    order_id, item_ids, supplier_id = _seed_order_with_items(
        item_count=1,
        ordered_qty=2,
        order_uom="CTN",
        purchase_uom="CTN",
        invoice_uom="KG",
        is_catch_weight=True,
    )
    db = TestingSessionLocal()
    item = db.query(OrderItem).filter(OrderItem.id == item_ids[0]).one()
    db.add(
        SupplierAllocation(
            order_item_id=item.id,
            final_supplier_id=supplier_id,
            final_qty=2,
            final_uom="CTN",
        )
    )
    db.flush()
    assert item.actual_weight_kg is None
    assert evaluate_order_allocation_completion(db, order_id).complete is True
    order = db.query(Order).filter(Order.id == order_id).one()
    synchronize_confirmed_order_allocation_status(db, order)
    assert order.status == OrderStatus.allocated
    assert item.line_status == LineStatus.allocated
    item.actual_weight_kg = 21.73
    db.flush()
    assert evaluate_order_allocation_completion(db, order_id).complete is True
    synchronize_confirmed_order_allocation_status(db, order)
    assert order.status == OrderStatus.allocated
    assert item.line_status == LineStatus.allocated
    db.rollback()
    db.close()


def test_order_purchase_uom_mismatch_requires_master_correction():
    order_id, item_ids, supplier_id = _seed_order_with_items(
        item_count=1,
        order_uom="PC",
        purchase_uom="kg",
        invoice_uom="kg",
    )
    db = TestingSessionLocal()
    db.add(
        SupplierAllocation(
            order_item_id=item_ids[0],
            final_supplier_id=supplier_id,
            final_qty=5,
            final_uom="kg",
        )
    )
    db.flush()
    result = evaluate_order_allocation_completion(db, order_id)
    assert result.complete is False
    assert "UOM_MISMATCH_REQUIRES_MASTER_CORRECTION" in {reason.code for reason in result.reasons}
    db.rollback()
    db.close()


def test_manual_confirmed_to_allocated_rejects_missing_and_partial_allocations():
    order_id, item_ids, supplier_id = _seed_order_with_items(item_count=2)
    client = _client()

    missing = client.post(
        f"/api/v1/orders/{order_id}/bulk-transition",
        json={"from_status": "confirmed", "to_status": "allocated"},
    )
    assert missing.status_code == 409
    assert missing.json()["detail"]["code"] == "ALLOCATION_INCOMPLETE"

    db = TestingSessionLocal()
    db.add(
        SupplierAllocation(
            order_item_id=item_ids[0],
            final_supplier_id=supplier_id,
            final_qty=5,
            final_uom="count",
        )
    )
    db.commit()
    db.close()

    partial = client.post(
        f"/api/v1/orders/{order_id}/bulk-transition",
        json={"from_status": "confirmed", "to_status": "allocated"},
    )
    assert partial.status_code == 409
    assert partial.json()["detail"]["code"] == "ALLOCATION_INCOMPLETE"


def test_manual_confirmed_to_allocated_rejects_master_uom_mismatch():
    order_id, item_ids, supplier_id = _seed_order_with_items(
        item_count=1,
        order_uom="PC",
        purchase_uom="kg",
        invoice_uom="kg",
    )
    db = TestingSessionLocal()
    db.add(
        SupplierAllocation(
            order_item_id=item_ids[0],
            final_supplier_id=supplier_id,
            final_qty=5,
            final_uom="kg",
        )
    )
    db.commit()
    db.close()

    response = _client().post(
        f"/api/v1/orders/{order_id}/bulk-transition",
        json={"from_status": "confirmed", "to_status": "allocated"},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "ALLOCATION_INCOMPLETE"
    assert "UOM_MISMATCH_REQUIRES_MASTER_CORRECTION" in {
        detail["code"] for detail in response.json()["detail"]["details"]
    }


def test_manual_confirmed_to_allocated_succeeds_when_complete_and_preserves_cancelled_item():
    order_id, item_ids, supplier_id = _seed_order_with_items(item_count=2)
    db = TestingSessionLocal()
    cancelled_item = db.query(OrderItem).filter(OrderItem.id == item_ids[1]).one()
    cancelled_item.line_status = LineStatus.cancelled
    db.add(
        SupplierAllocation(
            order_item_id=item_ids[0],
            final_supplier_id=supplier_id,
            final_qty=5,
            final_uom="count",
        )
    )
    db.commit()
    db.close()

    response = _client().post(
        f"/api/v1/orders/{order_id}/bulk-transition",
        json={"from_status": "confirmed", "to_status": "allocated"},
    )
    assert response.status_code == 200
    assert response.json()["updated_lines"] == 1

    db = TestingSessionLocal()
    order = db.query(Order).filter(Order.id == order_id).one()
    active_item = db.query(OrderItem).filter(OrderItem.id == item_ids[0]).one()
    cancelled_item = db.query(OrderItem).filter(OrderItem.id == item_ids[1]).one()
    assert order.status == OrderStatus.allocated
    assert active_item.line_status == LineStatus.allocated
    assert cancelled_item.line_status == LineStatus.cancelled
    db.close()


def test_manual_confirmed_to_allocated_succeeds_when_all_active_items_are_complete():
    order_id, item_ids, supplier_id = _seed_order_with_items(item_count=2)
    db = TestingSessionLocal()
    for item_id in item_ids:
        db.add(
            SupplierAllocation(
                order_item_id=item_id,
                final_supplier_id=supplier_id,
                final_qty=5,
                final_uom="count",
            )
        )
    db.commit()
    db.close()

    response = _client().post(
        f"/api/v1/orders/{order_id}/bulk-transition",
        json={"from_status": "confirmed", "to_status": "allocated"},
    )
    assert response.status_code == 200
    assert response.json()["updated_lines"] == 2

    db = TestingSessionLocal()
    assert db.query(Order).filter(Order.id == order_id).one().status == OrderStatus.allocated
    assert all(
        item.line_status == LineStatus.allocated
        for item in db.query(OrderItem).filter(OrderItem.order_id == order_id).all()
    )
    db.close()


def test_split_allocation_completion_requires_exact_total_and_matching_uom():
    for quantities, expected_complete in (((6, 4), True), ((6, 3), False), ((6, 5), False)):
        order_id, item_ids, supplier_id = _seed_order_with_items(item_count=1, ordered_qty=10)
        db = TestingSessionLocal()
        parent = SupplierAllocation(
            order_item_id=item_ids[0],
            final_supplier_id=supplier_id,
            final_qty=10,
            final_uom="count",
            split_group_id=f"split-{order_id}",
            is_split_child=False,
        )
        db.add(parent)
        db.flush()
        for quantity in quantities:
            db.add(
                SupplierAllocation(
                    order_item_id=item_ids[0],
                    final_supplier_id=supplier_id,
                    final_qty=quantity,
                    final_uom="count",
                    split_group_id=parent.split_group_id,
                    parent_allocation_id=parent.id,
                    is_split_child=True,
                )
            )
        db.flush()
        order = db.query(Order).filter(Order.id == order_id).one()
        result = synchronize_confirmed_order_allocation_status(db, order)
        assert result.complete is expected_complete
        assert order.status == (OrderStatus.allocated if expected_complete else OrderStatus.confirmed)
        if not expected_complete:
            assert "FINAL_QTY_MISMATCH" in {reason.code for reason in result.reasons}
        db.rollback()
        db.close()


def test_bulk_save_rejects_orders_outside_confirmed_status():
    cases = (
        (OrderStatus.allocated, LineStatus.allocated),
        (OrderStatus.purchased, LineStatus.purchased),
        (OrderStatus.shipped, LineStatus.shipped),
        (OrderStatus.invoiced, LineStatus.invoiced),
    )
    client = _client()
    for order_status, line_status in cases:
        order_id, item_ids, supplier_id = _seed_order_with_items(item_count=1, order_status=order_status)
        db = TestingSessionLocal()
        item = db.query(OrderItem).filter(OrderItem.id == item_ids[0]).one()
        item.line_status = line_status
        allocation = SupplierAllocation(
            order_item_id=item.id,
            final_supplier_id=supplier_id,
            final_qty=4,
            final_uom="count",
        )
        db.add(allocation)
        db.commit()
        allocation_id = allocation.id
        db.close()

        response = client.post(
            "/api/v1/order-item-allocations/bulk-save",
            json={"items": [{"order_item_id": item_ids[0], "supplier_id": supplier_id, "allocated_qty": 5}]},
        )
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "ORDER_NOT_ALLOCATION_EDITABLE"
        db = TestingSessionLocal()
        order = db.query(Order).filter(Order.id == order_id).one()
        item = db.query(OrderItem).filter(OrderItem.id == item_ids[0]).one()
        allocation = db.query(SupplierAllocation).filter(SupplierAllocation.id == allocation_id).one()
        assert order.status == order_status
        assert item.line_status == line_status
        assert float(allocation.final_qty) == 4
        db.close()


def test_cancelled_order_rejects_allocation_save():
    order_id, item_ids, supplier_id = _seed_order_with_items(item_count=1, order_status=OrderStatus.cancelled)
    db = TestingSessionLocal()
    item = db.query(OrderItem).filter(OrderItem.id == item_ids[0]).one()
    item.line_status = LineStatus.cancelled
    db.commit()
    db.close()

    response = _client().post(
        "/api/v1/order-item-allocations/bulk-save",
        json={"items": [{"order_item_id": item_ids[0], "supplier_id": supplier_id, "allocated_qty": 5}]},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "ORDER_NOT_ALLOCATION_EDITABLE"

    db = TestingSessionLocal()
    assert db.query(SupplierAllocation).filter(SupplierAllocation.order_item_id == item_ids[0]).count() == 0
    assert db.query(Order).filter(Order.id == order_id).one().status == OrderStatus.cancelled
    db.close()
