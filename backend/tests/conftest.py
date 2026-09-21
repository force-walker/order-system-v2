"""Give existing business tests real, DB-backed sessions without bypassing auth.

Authentication tests deliberately use anonymous clients and their own isolated DB.
"""
from itertools import count

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.auth import hash_password, issue_tokens
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.auth import User
from app.models.entities import Delivery, DeliveryItem, Invoice, InvoiceItem, Order, OrderItem


_SQLITE_TEST_DOCUMENT_SEQ = count(900_000_000)
_SQLITE_TEST_LINE_SEQ = count(900_000_000)


@event.listens_for(Session, "before_flush")
def supply_permanent_numbers_for_legacy_sqlite_fixtures(session, _flush_context, _instances):
    """Keep direct legacy test seeds valid after production metadata became NOT NULL.

    Application creation paths allocate authoritative values before flush. This
    SQLite-only listener is test support for older fixtures which construct ORM
    rows directly; it never runs against PostgreSQL or production sessions.
    """
    if session.get_bind().dialect.name != "sqlite":
        return

    for row in tuple(session.new):
        if isinstance(row, (Order, Delivery, Invoice)):
            if row.document_seq is None:
                row.document_seq = next(_SQLITE_TEST_DOCUMENT_SEQ)
            if row.next_line_no is None:
                row.next_line_no = 10

    detail_specs = (
        (OrderItem, "ODL", "order_line_no"),
        (DeliveryItem, "DLI", "delivery_line_no"),
        (InvoiceItem, "IVL", "invoice_line_no"),
    )
    for row in tuple(session.new):
        for model, prefix, compatibility_field in detail_specs:
            if not isinstance(row, model):
                continue
            synthetic = next(_SQLITE_TEST_LINE_SEQ)
            if row.line_no is None:
                row.line_no = synthetic
            if row.line_ref is None:
                row.line_ref = f"{prefix}-T{synthetic:016d}"
            if not getattr(row, compatibility_field, None):
                setattr(row, compatibility_field, row.line_ref)
            break


LEGACY_BUSINESS_MODULES = {
    "test_allocations_purchase_results_api", "test_api_regression_matrix", "test_audit_metrics_api",
    "test_batch_api", "test_customers_orders_api", "test_deliveries_api", "test_error_payload_contract_api",
    "test_error_policy_409_422_api", "test_invoices_api", "test_order_item_bulk_allocations_api",
    "test_order_items_api", "test_products_api", "test_products_bulk_api", "test_reports_shipping_api",
    "test_supplier_product_mappings_api", "test_suppliers_api", "test_system_settings_api",
    "test_validation_boundaries_api",
}


@pytest.fixture(autouse=True)
def business_test_session(request, monkeypatch):
    if request.module.__name__.split('.')[-1] not in LEGACY_BUSINESS_MODULES:
        yield
        return
    previous = app.dependency_overrides.copy()
    engine = getattr(request.module, "engine", None)
    owns_engine = engine is None
    if owns_engine:
        engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)

    def db_override():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = db_override

    def test_tokens(user_id="business-test", role="admin"):
        with Session(engine) as db:
            user = db.get(User, user_id)
            if user is None:
                user = User(user_id=user_id, role=role, password_hash=hash_password("test-only-password"), email_verified=True)
                db.add(user)
            user.role = role
            db.flush()
            tokens = issue_tokens(user_id, role, db)
            db.commit()
            return tokens

    # Legacy role-based test helpers now create real test users and sessions.
    if hasattr(request.module, "issue_tokens"):
        monkeypatch.setattr(request.module, "issue_tokens", test_tokens)
    access, _, _ = test_tokens()
    original_request = TestClient.request

    def authenticated_request(self, method, url, **kwargs):
        headers = dict(kwargs.get("headers") or {})
        if not any(key.lower() == "authorization" for key in headers):
            headers["Authorization"] = "Bearer " + access
        kwargs["headers"] = headers
        return original_request(self, method, url, **kwargs)

    monkeypatch.setattr(TestClient, "request", authenticated_request)
    yield
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous)
    if owns_engine:
        engine.dispose()
