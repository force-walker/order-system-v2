"""Permanent numbering regression tests.

The PostgreSQL cases use only uniquely named rows and remove them afterward.
They are skipped unless TEST_POSTGRES_URL is explicitly provided.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
import os
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.core.numbering import (
    ensure_delivery_header_numbers,
    ensure_delivery_item_number,
    ensure_invoice_header_numbers,
    ensure_invoice_item_number,
    ensure_order_header_numbers,
    ensure_order_item_number,
    generate_official_invoice_no,
)
from app.db.base import Base
from app.models.entities import (
    Customer,
    Delivery,
    DeliveryItem,
    Invoice,
    InvoiceItem,
    InvoiceStatus,
    Order,
    OrderItem,
    OrderStatus,
    PricingBasis,
    Product,
)


def _engine():
    url = os.getenv("TEST_POSTGRES_URL")
    if not url:
        pytest.skip("TEST_POSTGRES_URL required for PostgreSQL numbering regression")
    engine = create_engine(url)
    assert engine.dialect.name == "postgresql"
    return engine


def _seed_master(db: Session, marker: str) -> tuple[int, int]:
    customer = Customer(customer_code=f"NUM-{marker}", name="Numbering Test", active=True)
    product = Product(
        sku=f"NUM-{marker}",
        name="Numbering Test Product",
        order_uom="count",
        purchase_uom="count",
        invoice_uom="count",
        active=True,
    )
    db.add_all([customer, product])
    db.flush()
    return customer.id, product.id


def _new_order(db: Session, customer_id: int, product_id: int, when: datetime, lines: int = 1) -> Order:
    order = Order(
        order_no="pending-test",
        customer_id=customer_id,
        order_datetime=when,
        delivery_date=when.date(),
        status=OrderStatus.new,
        created_by="numbering-test",
        updated_by="numbering-test",
    )
    ensure_order_header_numbers(db, order)
    db.add(order)
    db.flush()
    for _ in range(lines):
        item = OrderItem(
            order_id=order.id,
            product_id=product_id,
            ordered_qty=1,
            order_uom_type=PricingBasis.uom_count,
            pricing_basis=PricingBasis.uom_count,
            unit_price_uom_count=100,
        )
        ensure_order_item_number(db, order, item)
        db.add(item)
        db.flush()
    return order


def _cleanup(engine, marker: str) -> None:
    with engine.begin() as connection:
        customer_id = connection.scalar(text("SELECT id FROM customers WHERE customer_code=:code"), {"code": f"NUM-{marker}"})
        if customer_id is None:
            return
        order_ids = [row[0] for row in connection.execute(text("SELECT id FROM orders WHERE customer_id=:id"), {"id": customer_id})]
        invoice_ids = [row[0] for row in connection.execute(text("SELECT id FROM invoices WHERE customer_id=:id"), {"id": customer_id})]
        delivery_ids = [row[0] for row in connection.execute(text("SELECT id FROM deliveries WHERE customer_id=:id"), {"id": customer_id})]
        if invoice_ids:
            connection.execute(text("DELETE FROM invoice_items WHERE invoice_id=ANY(:ids)"), {"ids": invoice_ids})
            connection.execute(text("DELETE FROM invoices WHERE id=ANY(:ids)"), {"ids": invoice_ids})
        if delivery_ids:
            connection.execute(text("DELETE FROM delivery_items WHERE delivery_id=ANY(:ids)"), {"ids": delivery_ids})
            connection.execute(text("DELETE FROM deliveries WHERE id=ANY(:ids)"), {"ids": delivery_ids})
        if order_ids:
            connection.execute(text("DELETE FROM order_items WHERE order_id=ANY(:ids)"), {"ids": order_ids})
            connection.execute(text("DELETE FROM orders WHERE id=ANY(:ids)"), {"ids": order_ids})
        connection.execute(text("DELETE FROM products WHERE sku=:sku"), {"sku": f"NUM-{marker}"})
        connection.execute(text("DELETE FROM customers WHERE id=:id"), {"id": customer_id})


def test_document_and_line_numbering_does_not_reset_by_date():
    engine = _engine()
    marker = uuid4().hex[:12]
    try:
        with Session(engine) as db:
            customer_id, product_id = _seed_master(db, marker)
            first = _new_order(db, customer_id, product_id, datetime(2026, 9, 20, tzinfo=UTC), lines=2)
            second = _new_order(db, customer_id, product_id, datetime(2027, 1, 1, tzinfo=UTC))
            db.commit()
            first_items = db.query(OrderItem).filter(OrderItem.order_id == first.id).order_by(OrderItem.line_no).all()
            assert second.document_seq == first.document_seq + 1
            assert second.order_no == f"ORD-{second.document_seq:08d}"
            assert [(row.line_no, row.line_ref) for row in first_items] == [
                (10, f"ODL-{first.document_seq:08d}-0010"),
                (20, f"ODL-{first.document_seq:08d}-0020"),
            ]
            assert all(row.order_line_no == row.line_ref for row in first_items)

            inserted = OrderItem(
                order_id=first.id,
                product_id=product_id,
                ordered_qty=1,
                order_uom_type=PricingBasis.uom_count,
                pricing_basis=PricingBasis.uom_count,
                unit_price_uom_count=100,
                line_no=15,
                line_ref=f"ODL-{first.document_seq:08d}-0015",
                order_line_no=f"ODL-{first.document_seq:08d}-0015",
            )
            db.add(inserted)
            db.commit()
            assert inserted.line_no == 15
            inserted.line_no = 25
            with pytest.raises(DBAPIError):
                db.commit()
            db.rollback()
            assert db.get(OrderItem, inserted.id).line_no == 15
    finally:
        _cleanup(engine, marker)
        engine.dispose()


def test_concurrent_order_numbering_is_unique():
    engine = _engine()
    marker = uuid4().hex[:12]
    try:
        with Session(engine) as db:
            customer_id, product_id = _seed_master(db, marker)
            db.commit()

        def create_one(offset: int) -> tuple[int, int, str]:
            with Session(engine) as db:
                order = _new_order(db, customer_id, product_id, datetime.now(UTC) + timedelta(days=offset))
                db.commit()
                return int(order.document_seq), int(order.legacy_id), str(order.order_no)

        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(create_one, range(4)))
        assert len({row[0] for row in results}) == 4
        assert len({row[1] for row in results}) == 4
        assert len({row[2] for row in results}) == 4
    finally:
        _cleanup(engine, marker)
        engine.dispose()


def test_empty_header_and_last_detail_delete_are_rejected():
    engine = _engine()
    marker = uuid4().hex[:12]
    try:
        with Session(engine) as db:
            customer_id, product_id = _seed_master(db, marker)
            db.commit()
        with Session(engine) as db:
            empty = Order(
                order_no="pending-empty",
                customer_id=customer_id,
                order_datetime=datetime.now(UTC),
                delivery_date=date.today(),
                status=OrderStatus.new,
                created_by="numbering-test",
                updated_by="numbering-test",
            )
            ensure_order_header_numbers(db, empty)
            db.add(empty)
            with pytest.raises(DBAPIError):
                db.commit()
            db.rollback()
            assert db.get(Order, empty.id) is None

        with Session(engine) as db:
            order = _new_order(db, customer_id, product_id, datetime.now(UTC))
            db.commit()
            item = db.query(OrderItem).filter(OrderItem.order_id == order.id).one()
            db.delete(item)
            with pytest.raises(DBAPIError):
                db.commit()
            db.rollback()
            assert db.query(OrderItem).filter(OrderItem.order_id == order.id).count() == 1
    finally:
        _cleanup(engine, marker)
        engine.dispose()


def test_model_metadata_matches_permanent_numbering_nullability():
    for table, columns in (
        ("orders", ("document_seq", "next_line_no")),
        ("deliveries", ("document_seq", "next_line_no")),
        ("invoices", ("document_seq", "next_line_no")),
        ("order_items", ("line_no", "line_ref")),
        ("delivery_items", ("line_no", "line_ref")),
        ("invoice_items", ("line_no", "line_ref")),
    ):
        assert all(Base.metadata.tables[table].c[column].nullable is False for column in columns)
    assert Base.metadata.tables["invoices"].c.official_document_seq.nullable is True


def test_concurrent_last_two_detail_deletes_leave_one_detail():
    engine = _engine()
    marker = uuid4().hex[:12]
    try:
        with Session(engine) as db:
            customer_id, product_id = _seed_master(db, marker)
            order = _new_order(db, customer_id, product_id, datetime.now(UTC), lines=2)
            db.commit()
            order_id = order.id
            item_ids = [
                row[0]
                for row in db.execute(
                    text("SELECT id FROM order_items WHERE order_id=:id ORDER BY line_no"),
                    {"id": order_id},
                )
            ]

        ready = Barrier(2)

        def delete_one(item_id: str) -> str:
            connection = engine.connect()
            transaction = connection.begin()
            try:
                connection.execute(text("DELETE FROM order_items WHERE id=:id"), {"id": item_id})
                ready.wait(timeout=10)
                transaction.commit()
                return "committed"
            except DBAPIError:
                if transaction.is_active:
                    transaction.rollback()
                return "rejected"
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(delete_one, item_ids))

        assert sorted(results) == ["committed", "rejected"]
        with engine.connect() as connection:
            assert connection.scalar(
                text("SELECT COUNT(*) FROM order_items WHERE order_id=:id"),
                {"id": order_id},
            ) == 1
    finally:
        _cleanup(engine, marker)
        engine.dispose()


def test_complete_aggregate_delete_is_allowed_and_cascade_semantics_do_not_conflict():
    engine = _engine()
    marker = uuid4().hex[:12]
    try:
        # The current schema deliberately uses the PostgreSQL default NO ACTION,
        # not ON DELETE CASCADE, for all three Header -> Detail relationships.
        schema = inspect(engine)
        for table, parent in (
            ("order_items", "orders"),
            ("delivery_items", "deliveries"),
            ("invoice_items", "invoices"),
        ):
            fk = next(row for row in schema.get_foreign_keys(table) if row["referred_table"] == parent)
            assert fk.get("options", {}).get("ondelete") in (None, "NO ACTION")

        with Session(engine) as db:
            customer_id, product_id = _seed_master(db, marker)
            order = _new_order(db, customer_id, product_id, datetime.now(UTC))
            order_item = db.query(OrderItem).filter(OrderItem.order_id == order.id).one()

            delivery = Delivery(
                delivery_no="pending",
                order_id=order.id,
                customer_id=customer_id,
                delivery_date=date.today(),
                shipped_date=date.today(),
            )
            ensure_delivery_header_numbers(db, delivery)
            db.add(delivery)
            db.flush()
            delivery_item = DeliveryItem(
                delivery_id=delivery.id,
                order_item_id=order_item.id,
                product_id=product_id,
                delivery_line_no="pending",
                delivered_qty=1,
                delivered_uom="count",
                shipped_date=date.today(),
            )
            ensure_delivery_item_number(db, delivery, delivery_item)
            db.add(delivery_item)

            invoice = Invoice(
                invoice_no="pending-invoice-delete",
                delivery_id=delivery.id,
                customer_id=customer_id,
                invoice_date=date.today(),
                delivery_date=date.today(),
                subtotal=100,
                tax_total=0,
                grand_total=100,
                status=InvoiceStatus.draft,
                is_locked=False,
            )
            ensure_invoice_header_numbers(db, invoice)
            db.add(invoice)
            db.flush()
            invoice_item = InvoiceItem(
                invoice_id=invoice.id,
                order_item_id=order_item.id,
                billable_qty=1,
                billable_uom="count",
                sales_unit_price=100,
                line_amount=100,
                tax_amount=0,
            )
            ensure_invoice_item_number(db, invoice, invoice_item)
            db.add(invoice_item)
            db.commit()
            order_id = order.id
            delivery_id = delivery.id
            invoice_id = invoice.id

            # Explicit Detail -> Header SQL in one transaction is valid. Do not
            # rely on ORM flush ordering because these models have no relationship().
            db.execute(text("DELETE FROM invoice_items WHERE id=:id"), {"id": invoice_item.id})
            db.execute(text("DELETE FROM invoices WHERE id=:id"), {"id": invoice.id})
            db.execute(text("DELETE FROM delivery_items WHERE id=:id"), {"id": delivery_item.id})
            db.execute(text("DELETE FROM deliveries WHERE id=:id"), {"id": delivery.id})
            db.execute(text("DELETE FROM order_items WHERE id=:id"), {"id": order_item.id})
            db.execute(text("DELETE FROM orders WHERE id=:id"), {"id": order.id})
            db.commit()
            assert db.get(Order, order_id) is None
            assert db.get(Delivery, delivery_id) is None
            assert db.get(Invoice, invoice_id) is None

        # Although CASCADE is not configured today, exercise all three actual
        # triggers under CASCADE inside rollback-only transactional DDL. Each
        # deferred child trigger must see that its Header is also gone.
        with Session(engine) as db:
            cascade_order = _new_order(db, customer_id, product_id, datetime.now(UTC))
            cascade_order_item = db.query(OrderItem).filter(OrderItem.order_id == cascade_order.id).one()
            cascade_delivery = Delivery(
                delivery_no="pending",
                order_id=cascade_order.id,
                customer_id=customer_id,
                delivery_date=date.today(),
                shipped_date=date.today(),
            )
            ensure_delivery_header_numbers(db, cascade_delivery)
            db.add(cascade_delivery)
            db.flush()
            cascade_delivery_item = DeliveryItem(
                delivery_id=cascade_delivery.id,
                order_item_id=cascade_order_item.id,
                product_id=product_id,
                delivery_line_no="pending",
                delivered_qty=1,
                delivered_uom="count",
                shipped_date=date.today(),
            )
            ensure_delivery_item_number(db, cascade_delivery, cascade_delivery_item)
            db.add(cascade_delivery_item)
            cascade_invoice = Invoice(
                invoice_no="pending-invoice-cascade",
                delivery_id=cascade_delivery.id,
                customer_id=customer_id,
                invoice_date=date.today(),
                delivery_date=date.today(),
                subtotal=100,
                tax_total=0,
                grand_total=100,
                status=InvoiceStatus.draft,
                is_locked=False,
            )
            ensure_invoice_header_numbers(db, cascade_invoice)
            db.add(cascade_invoice)
            db.flush()
            cascade_invoice_item = InvoiceItem(
                invoice_id=cascade_invoice.id,
                order_item_id=cascade_order_item.id,
                billable_qty=1,
                billable_uom="count",
                sales_unit_price=100,
                line_amount=100,
                tax_amount=0,
            )
            ensure_invoice_item_number(db, cascade_invoice, cascade_invoice_item)
            db.add(cascade_invoice_item)
            db.commit()
            cascade_order_id = cascade_order.id
            cascade_delivery_id = cascade_delivery.id
            cascade_invoice_id = cascade_invoice.id

        connection = engine.connect()
        transaction = connection.begin()
        try:
            for child, child_fk, parent in (
                ("order_items", "order_id", "orders"),
                ("delivery_items", "delivery_id", "deliveries"),
                ("invoice_items", "invoice_id", "invoices"),
            ):
                fk = next(
                    row
                    for row in inspect(connection).get_foreign_keys(child)
                    if row["referred_table"] == parent
                )
                constraint_name = connection.dialect.identifier_preparer.quote(fk["name"])
                connection.execute(text(f"ALTER TABLE {child} DROP CONSTRAINT {constraint_name}"))
                connection.execute(
                    text(
                        f"ALTER TABLE {child} ADD CONSTRAINT {constraint_name} "
                        f"FOREIGN KEY ({child_fk}) REFERENCES {parent}(id) ON DELETE CASCADE"
                    )
                )
            connection.execute(text("DELETE FROM invoices WHERE id=:id"), {"id": cascade_invoice_id})
            connection.execute(text("DELETE FROM deliveries WHERE id=:id"), {"id": cascade_delivery_id})
            connection.execute(text("DELETE FROM orders WHERE id=:id"), {"id": cascade_order_id})
            connection.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))
            for child, child_fk, parent_id in (
                ("order_items", "order_id", cascade_order_id),
                ("delivery_items", "delivery_id", cascade_delivery_id),
                ("invoice_items", "invoice_id", cascade_invoice_id),
            ):
                assert connection.scalar(
                    text(f"SELECT COUNT(*) FROM {child} WHERE {child_fk}=:id"),
                    {"id": parent_id},
                ) == 0
        finally:
            transaction.rollback()
            connection.close()
    finally:
        _cleanup(engine, marker)
        engine.dispose()


def test_invoice_draft_finalize_reset_refinalize_reuses_official_number():
    engine = _engine()
    marker = uuid4().hex[:12]
    try:
        with Session(engine) as db:
            customer_id, product_id = _seed_master(db, marker)
            order = _new_order(db, customer_id, product_id, datetime.now(UTC))
            order_item = db.query(OrderItem).filter(OrderItem.order_id == order.id).one()
            invoice = Invoice(
                invoice_no="pending-invoice",
                customer_id=customer_id,
                invoice_date=date.today(),
                delivery_date=date.today(),
                subtotal=100,
                tax_total=0,
                grand_total=100,
                status=InvoiceStatus.draft,
                is_locked=False,
            )
            ensure_invoice_header_numbers(db, invoice)
            db.add(invoice)
            db.flush()
            item = InvoiceItem(
                invoice_id=invoice.id,
                order_item_id=order_item.id,
                billable_qty=1,
                billable_uom="count",
                sales_unit_price=100,
                line_amount=100,
                tax_amount=0,
            )
            ensure_invoice_item_number(db, invoice, item)
            db.add(item)
            db.commit()

            draft_no = invoice.invoice_draft_no
            assert draft_no == f"IVD-{invoice.document_seq:08d}"
            assert invoice.official_document_seq is None
            invoice.official_invoice_no = generate_official_invoice_no(db, invoice)
            invoice.invoice_no = invoice.official_invoice_no
            invoice.status = InvoiceStatus.finalized
            invoice.is_locked = True
            db.commit()
            official_no = invoice.official_invoice_no

            invoice.invoice_no = draft_no
            invoice.status = InvoiceStatus.draft
            invoice.is_locked = False
            db.commit()
            invoice.invoice_no = invoice.official_invoice_no or generate_official_invoice_no(db, invoice)
            invoice.status = InvoiceStatus.finalized
            invoice.is_locked = True
            db.commit()
            assert invoice.invoice_no == official_no
            assert invoice.official_invoice_no == official_no
            assert official_no == f"INV-{invoice.official_document_seq:08d}"
    finally:
        _cleanup(engine, marker)
        engine.dispose()


def test_header_business_numbers_are_immutable_and_match_sequences():
    engine = _engine()
    marker = uuid4().hex[:12]
    try:
        with Session(engine) as db:
            customer_id, product_id = _seed_master(db, marker)
            order = _new_order(db, customer_id, product_id, datetime.now(UTC))
            order_item = db.query(OrderItem).filter(OrderItem.order_id == order.id).one()
            delivery = Delivery(
                delivery_no="pending",
                order_id=order.id,
                customer_id=customer_id,
                delivery_date=date.today(),
                shipped_date=date.today(),
            )
            ensure_delivery_header_numbers(db, delivery)
            db.add(delivery)
            db.flush()
            delivery_item = DeliveryItem(
                delivery_id=delivery.id,
                order_item_id=order_item.id,
                product_id=product_id,
                delivery_line_no="pending",
                delivered_qty=1,
                delivered_uom="count",
                shipped_date=date.today(),
            )
            ensure_delivery_item_number(db, delivery, delivery_item)
            db.add(delivery_item)
            invoice = Invoice(
                invoice_no="pending-business-number-test",
                delivery_id=delivery.id,
                customer_id=customer_id,
                invoice_date=date.today(),
                delivery_date=date.today(),
                subtotal=100,
                tax_total=0,
                grand_total=100,
                status=InvoiceStatus.draft,
                is_locked=False,
            )
            ensure_invoice_header_numbers(db, invoice)
            db.add(invoice)
            db.flush()
            invoice_item = InvoiceItem(
                invoice_id=invoice.id,
                order_item_id=order_item.id,
                billable_qty=1,
                billable_uom="count",
                sales_unit_price=100,
                line_amount=100,
                tax_amount=0,
            )
            ensure_invoice_item_number(db, invoice, invoice_item)
            db.add(invoice_item)
            db.commit()
            ids = {"order": order.id, "delivery": delivery.id, "invoice": invoice.id}

        rejected_updates = (
            ("UPDATE orders SET order_no='ORD-99999999' WHERE id=:id", ids["order"]),
            ("UPDATE orders SET document_seq=document_seq+1000000 WHERE id=:id", ids["order"]),
            ("UPDATE deliveries SET delivery_no='DEL-99999999' WHERE id=:id", ids["delivery"]),
            ("UPDATE deliveries SET document_seq=document_seq+1000000 WHERE id=:id", ids["delivery"]),
            ("UPDATE invoices SET invoice_draft_no='IVD-99999999' WHERE id=:id", ids["invoice"]),
            ("UPDATE invoices SET document_seq=document_seq+1000000 WHERE id=:id", ids["invoice"]),
            (
                "UPDATE invoices SET official_document_seq=90000001, "
                "official_invoice_no='INV-90000002' WHERE id=:id",
                ids["invoice"],
            ),
        )
        for statement, row_id in rejected_updates:
            with pytest.raises(DBAPIError), engine.begin() as connection:
                connection.execute(text(statement), {"id": row_id})

        with Session(engine) as db:
            invoice = db.get(Invoice, ids["invoice"])
            assert invoice is not None
            official_no = generate_official_invoice_no(db, invoice)
            invoice.official_invoice_no = official_no
            db.commit()
            official_seq = invoice.official_document_seq
            assert official_no == f"INV-{official_seq:08d}"

        for statement in (
            "UPDATE invoices SET official_invoice_no='INV-99999999' WHERE id=:id",
            "UPDATE invoices SET official_document_seq=official_document_seq+1 WHERE id=:id",
        ):
            with pytest.raises(DBAPIError), engine.begin() as connection:
                connection.execute(text(statement), {"id": ids["invoice"]})
    finally:
        _cleanup(engine, marker)
        engine.dispose()
