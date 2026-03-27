from datetime import UTC, date, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.entities import Customer, Order, OrderItem, PricingBasis, Product


engine = create_engine(
    "sqlite+pysqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    future=True,
)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base.metadata.create_all(bind=engine)


def _seed_order_and_product():
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
        is_catch_weight=False,
        weight_capture_required=False,
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
    )
    db.add(o)
    db.flush()
    return db, o.id, p.id


def test_order_item_requires_uom_count_price_when_pricing_basis_uom_count():
    db, order_id, product_id = _seed_order_and_product()
    bad = OrderItem(
        order_id=order_id,
        product_id=product_id,
        ordered_qty=1,
        pricing_basis=PricingBasis.uom_count,
        unit_price_uom_count=None,
        unit_price_uom_kg=None,
    )
    db.add(bad)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_order_item_requires_uom_kg_price_when_pricing_basis_uom_kg():
    db, order_id, product_id = _seed_order_and_product()
    bad = OrderItem(
        order_id=order_id,
        product_id=product_id,
        ordered_qty=1,
        pricing_basis=PricingBasis.uom_kg,
        unit_price_uom_count=None,
        unit_price_uom_kg=None,
    )
    db.add(bad)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
