"""PostgreSQL concurrency coverage for allocation completion.

Skipped unless TEST_POSTGRES_URL points to a disposable/test database.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime
import os
from threading import Event
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.core.allocation_completion import synchronize_confirmed_order_allocation_status
from app.core.numbering import ensure_order_header_numbers, ensure_order_item_number
from app.models.entities import Customer, LineStatus, Order, OrderItem, OrderStatus, PricingBasis, Product, Supplier, SupplierAllocation


def _engine():
    url = os.getenv("TEST_POSTGRES_URL")
    if not url:
        pytest.skip("TEST_POSTGRES_URL required for PostgreSQL allocation concurrency regression")
    engine = create_engine(url)
    assert engine.dialect.name == "postgresql"
    return engine


def test_concurrent_last_two_allocations_serialize_and_promote_order_once_complete():
    engine = _engine()
    marker = "ALLOC-" + uuid4().hex[:12]
    order_id: str | None = None
    customer_id: int | None = None
    product_id: int | None = None
    supplier_id: int | None = None
    try:
        with Session(engine) as db:
            customer = Customer(customer_code=marker, name="Allocation Concurrency Customer", active=True)
            product = Product(
                sku=marker,
                name="Allocation Concurrency Product",
                order_uom="count",
                purchase_uom="count",
                invoice_uom="count",
                is_catch_weight=False,
                weight_capture_required=False,
                pricing_basis_default=PricingBasis.uom_count,
                active=True,
            )
            supplier = Supplier(supplier_code=marker, name="Allocation Concurrency Supplier", active=True)
            db.add_all([customer, product, supplier])
            db.flush()
            customer_id, product_id, supplier_id = customer.id, product.id, supplier.id
            order = Order(
                order_no="pending-allocation-concurrency",
                customer_id=customer.id,
                order_datetime=datetime.now(UTC),
                delivery_date=date.today(),
                status=OrderStatus.confirmed,
                created_by="allocation-concurrency-test",
                updated_by="allocation-concurrency-test",
            )
            ensure_order_header_numbers(db, order)
            db.add(order)
            db.flush()
            order_id = order.id
            item_ids: list[str] = []
            for _ in range(2):
                item = OrderItem(
                    order_id=order.id,
                    product_id=product.id,
                    ordered_qty=5,
                    order_uom_type=PricingBasis.uom_count,
                    pricing_basis=PricingBasis.uom_count,
                    unit_price_uom_count=100,
                )
                ensure_order_item_number(db, order, item)
                db.add(item)
                db.flush()
                item_ids.append(item.id)
            db.commit()

        first_has_evaluated = Event()
        second_is_waiting_for_lock = Event()

        def save_first() -> str:
            with Session(engine) as db:
                order = db.query(Order).filter(Order.id == order_id).with_for_update().one()
                db.add(
                    SupplierAllocation(
                        order_item_id=item_ids[0],
                        final_supplier_id=supplier_id,
                        final_qty=5,
                        final_uom="count",
                    )
                )
                db.flush()
                result = synchronize_confirmed_order_allocation_status(db, order)
                assert result.complete is False
                assert order.status == OrderStatus.confirmed
                first_has_evaluated.set()
                assert second_is_waiting_for_lock.wait(timeout=10)
                db.commit()
                return "first-committed"

        def save_second() -> str:
            assert first_has_evaluated.wait(timeout=10)
            with Session(engine) as db:
                second_is_waiting_for_lock.set()
                order = db.query(Order).filter(Order.id == order_id).with_for_update().one()
                db.add(
                    SupplierAllocation(
                        order_item_id=item_ids[1],
                        final_supplier_id=supplier_id,
                        final_qty=5,
                        final_uom="count",
                    )
                )
                db.flush()
                result = synchronize_confirmed_order_allocation_status(db, order)
                assert result.complete is True
                assert order.status == OrderStatus.allocated
                db.commit()
                return "second-committed"

        with ThreadPoolExecutor(max_workers=2) as pool:
            first_future = pool.submit(save_first)
            second_future = pool.submit(save_second)
            assert first_future.result(timeout=20) == "first-committed"
            assert second_future.result(timeout=20) == "second-committed"

        with Session(engine) as db:
            order = db.query(Order).filter(Order.id == order_id).one()
            items = db.query(OrderItem).filter(OrderItem.order_id == order_id).all()
            assert order.status == OrderStatus.allocated
            assert all(item.line_status == LineStatus.allocated for item in items)
            assert db.query(SupplierAllocation).filter(SupplierAllocation.order_item_id.in_(item_ids)).count() == 2
    finally:
        if order_id is not None:
            with engine.begin() as connection:
                connection.execute(text("DELETE FROM audit_logs WHERE entity_id=:order_id OR entity_id IN (SELECT id FROM order_items WHERE order_id=:order_id)"), {"order_id": order_id})
                connection.execute(text("DELETE FROM supplier_allocations WHERE order_item_id IN (SELECT id FROM order_items WHERE order_id=:order_id)"), {"order_id": order_id})
                connection.execute(text("DELETE FROM order_items WHERE order_id=:order_id"), {"order_id": order_id})
                connection.execute(text("DELETE FROM orders WHERE id=:order_id"), {"order_id": order_id})
                if product_id is not None:
                    connection.execute(text("DELETE FROM products WHERE id=:id"), {"id": product_id})
                if customer_id is not None:
                    connection.execute(text("DELETE FROM customers WHERE id=:id"), {"id": customer_id})
                if supplier_id is not None:
                    connection.execute(text("DELETE FROM suppliers WHERE id=:id"), {"id": supplier_id})
        engine.dispose()
