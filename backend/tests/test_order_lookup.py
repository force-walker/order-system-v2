from datetime import UTC, date, datetime

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.routes_deliveries import _get_order_or_404 as delivery_lookup
from app.api.routes_invoices import _get_order_or_404 as invoice_lookup
from app.api.routes_orders import _get_order_by_identifier_or_404 as order_lookup
from app.db.base import Base
from app.models.entities import Customer, Order


@pytest.fixture
def db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        customer = Customer(customer_code="LOOKUP", name="Lookup test")
        session.add(customer)
        session.flush()
        for identifier, legacy_id in [("order-uuid", 42), ("42", 43)]:
            session.add(Order(
                id=identifier,
                legacy_id=legacy_id,
                order_no=f"ORDER-{identifier}",
                customer_id=customer.id,
                order_datetime=datetime.now(UTC),
                delivery_date=date.today(),
            ))
        session.commit()
        yield session
    engine.dispose()


@pytest.mark.parametrize("lookup", [order_lookup, invoice_lookup, delivery_lookup])
@pytest.mark.parametrize("identifier, expected_id", [
    ("order-uuid", "order-uuid"),
    (42, "42"),  # Primary ID takes precedence over a matching legacy ID.
    ("42", "42"),
    (43, "42"),
    ("043", "42"),  # Numeric strings retain the existing legacy fallback.
])
def test_lookup_identifier_compatibility(db, lookup, identifier, expected_id):
    assert lookup(db, identifier).id == expected_id


@pytest.mark.parametrize("lookup", [order_lookup, invoice_lookup, delivery_lookup])
@pytest.mark.parametrize("identifier", ["missing", "999", "-1", " 43"])
def test_lookup_preserves_not_found_error(db, lookup, identifier):
    with pytest.raises(HTTPException) as error:
        lookup(db, identifier)
    assert error.value.status_code == 404
    assert error.value.detail == {"code": "ORDER_NOT_FOUND", "message": "order not found"}
