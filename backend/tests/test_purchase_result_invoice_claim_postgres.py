"""PostgreSQL concurrency coverage for Purchase Result invoice claims."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime
import os
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.api.routes_invoices import generate_draft_from_purchase_results
from app.core.numbering import ensure_order_header_numbers, ensure_order_item_number
from app.models.entities import Customer, Order, OrderItem, OrderStatus, PricingBasis, Product, PurchaseResult, PurchaseResultStatus, SupplierAllocation, SystemSettings
from app.schemas.invoice import InvoiceDraftFromPurchaseResultsRequest


def _engine():
    url = os.getenv("TEST_POSTGRES_URL")
    if not url:
        pytest.skip("TEST_POSTGRES_URL required for PostgreSQL Purchase Result claim regression")
    engine = create_engine(url)
    assert engine.dialect.name == "postgresql"
    return engine


def test_concurrent_draft_generation_claims_purchase_result_once():
    engine = _engine()
    marker = "PR-CLAIM-" + uuid4().hex[:12]
    order_id: str | None = None
    customer_id: int | None = None
    product_id: int | None = None
    purchase_result_id: int | None = None
    try:
        with Session(engine) as db:
            if db.get(SystemSettings, 1) is None:
                pytest.skip("system settings row id=1 is required")
            customer = Customer(customer_code=marker, name="PR Claim Test", active=True)
            product = Product(
                sku=marker,
                name="PR Claim Test",
                order_uom="PC",
                purchase_uom="PC",
                invoice_uom="PC",
                is_catch_weight=False,
                weight_capture_required=False,
                pricing_basis_default=PricingBasis.uom_count,
                active=True,
            )
            db.add_all([customer, product])
            db.flush()
            customer_id, product_id = customer.id, product.id
            order = Order(
                order_no="pending-pr-claim",
                customer_id=customer.id,
                order_datetime=datetime.now(UTC),
                delivery_date=date.today(),
                status=OrderStatus.confirmed,
                created_by="pr-claim-test",
                updated_by="pr-claim-test",
            )
            ensure_order_header_numbers(db, order)
            db.add(order)
            db.flush()
            order_id = order.id
            item = OrderItem(
                order_id=order.id,
                product_id=product.id,
                ordered_qty=2,
                order_uom_type=PricingBasis.uom_count,
                pricing_basis=PricingBasis.uom_count,
                unit_price_uom_count=100,
            )
            ensure_order_item_number(db, order, item)
            db.add(item)
            db.flush()
            allocation = SupplierAllocation(order_item_id=item.id, final_qty=2, final_uom="PC")
            db.add(allocation)
            db.flush()
            result = PurchaseResult(
                allocation_id=allocation.id,
                purchased_qty=2,
                purchased_uom="PC",
                final_unit_cost=100,
                result_status=PurchaseResultStatus.filled,
                invoiceable_flag=True,
            )
            db.add(result)
            db.commit()
            purchase_result_id = result.id

        barrier = Barrier(2)

        def generate() -> tuple[int, str]:
            with Session(engine) as db:
                barrier.wait(timeout=10)
                try:
                    response = generate_draft_from_purchase_results(
                        InvoiceDraftFromPurchaseResultsRequest(
                            order_id=order_id,
                            invoice_date=date.today(),
                            purchase_result_ids=[purchase_result_id],
                        ),
                        db,
                    )
                    return 201, response.invoice_id
                except HTTPException as exc:
                    db.rollback()
                    return exc.status_code, exc.detail["code"]

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(generate), pool.submit(generate)]
            outcomes = sorted(future.result(timeout=20) for future in futures)

        assert [status for status, _ in outcomes] == [201, 409]
        assert outcomes[1][1] == "PURCHASE_RESULT_ALREADY_CLAIMED"
        with Session(engine) as db:
            result = db.get(PurchaseResult, purchase_result_id)
            assert result is not None and float(result.invoice_qty) == 2.0
    finally:
        if order_id is not None:
            with engine.begin() as connection:
                connection.execute(text("DELETE FROM audit_logs WHERE entity_id IN (SELECT id FROM invoices WHERE customer_id=:customer_id) OR entity_id=:order_id"), {"customer_id": customer_id, "order_id": order_id})
                connection.execute(text("DELETE FROM invoice_items WHERE invoice_id IN (SELECT id FROM invoices WHERE customer_id=:customer_id)"), {"customer_id": customer_id})
                connection.execute(text("DELETE FROM invoices WHERE customer_id=:customer_id"), {"customer_id": customer_id})
                connection.execute(text("DELETE FROM purchase_results WHERE allocation_id IN (SELECT id FROM supplier_allocations WHERE order_item_id IN (SELECT id FROM order_items WHERE order_id=:order_id))"), {"order_id": order_id})
                connection.execute(text("DELETE FROM supplier_allocations WHERE order_item_id IN (SELECT id FROM order_items WHERE order_id=:order_id)"), {"order_id": order_id})
                connection.execute(text("DELETE FROM order_items WHERE order_id=:order_id"), {"order_id": order_id})
                connection.execute(text("DELETE FROM orders WHERE id=:order_id"), {"order_id": order_id})
                connection.execute(text("DELETE FROM products WHERE id=:id"), {"id": product_id})
                connection.execute(text("DELETE FROM customers WHERE id=:id"), {"id": customer_id})
        engine.dispose()
