from datetime import UTC, date, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.entities import Customer, Invoice, InvoiceItem, InvoiceStatus, Order, OrderItem, OrderStatus, PricingBasis, Product


engine = create_engine(
    "sqlite+pysqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    future=True,
)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base.metadata.create_all(bind=engine)


def _seed_invoice_and_order_item():
    db = TestingSessionLocal()
    c = Customer(customer_code=f"C-{datetime.now(UTC).timestamp()}", name="C", active=True)
    db.add(c)
    db.flush()

    p = Product(
        sku=f"SKU-{datetime.now(UTC).timestamp()}",
        name="P",
        order_uom="count",
        purchase_uom="count",
        invoice_uom="count",
        pricing_basis_default=PricingBasis.uom_count,
        active=True,
    )
    db.add(p)
    db.flush()

    o = Order(
        order_no=f"ORD-{datetime.now(UTC).timestamp()}",
        customer_id=c.id,
        order_datetime=datetime.now(UTC),
        delivery_date=date.today(),
        status=OrderStatus.confirmed,
    )
    db.add(o)
    db.flush()

    oi = OrderItem(
        order_id=o.id,
        product_id=p.id,
        ordered_qty=1,
        pricing_basis=PricingBasis.uom_count,
        unit_price_uom_count=100,
        order_uom_type=PricingBasis.uom_count,
    )
    db.add(oi)
    db.flush()

    inv = Invoice(
        invoice_no=f"INV-{datetime.now(UTC).timestamp()}",
        customer_id=c.id,
        invoice_date=date.today(),
        delivery_date=date.today(),
        status=InvoiceStatus.draft,
    )
    db.add(inv)
    db.flush()

    return db, inv.id, oi.id


def test_invoice_item_insert_success():
    db, invoice_id, order_item_id = _seed_invoice_and_order_item()
    item = InvoiceItem(
        invoice_id=invoice_id,
        order_item_id=order_item_id,
        billable_qty=1,
        billable_uom="count",
        sales_unit_price=120,
        line_amount=120,
        tax_amount=12,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    assert item.id > 0


def test_invoice_item_sales_unit_price_non_negative():
    db, invoice_id, order_item_id = _seed_invoice_and_order_item()
    bad = InvoiceItem(
        invoice_id=invoice_id,
        order_item_id=order_item_id,
        billable_qty=1,
        billable_uom="count",
        sales_unit_price=-1,
        line_amount=120,
        tax_amount=12,
    )
    db.add(bad)
    with pytest.raises(IntegrityError):
        db.commit()
