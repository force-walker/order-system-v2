from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.auth import issue_tokens
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.entities import AuditLog


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


def _auth(role: str = "admin") -> dict[str, str]:
    access, _, _ = issue_tokens("auditor", role)
    return {"Authorization": f"Bearer {access}"}


def test_metrics_endpoint_and_summary():
    client = _client()
    res = client.get("/api/v1/metrics")
    assert res.status_code == 200
    assert "order_system_v2_api_requests_total" in res.text

    summary = client.get("/api/v1/ops/metrics/summary", headers=_auth("admin"))
    assert summary.status_code == 200
    body = summary.json()
    assert "api" in body and "worker" in body and "db" in body
    assert "errors4xxTotal" in body["api"]
    assert "errors5xxTotal" in body["api"]
    assert "statusFamilyCounts" in body["api"]
    assert "endpointLatencyP95Ms" in body["api"]
    assert "endpointStatusCounts" in body["api"]


def test_audit_logs_list_detail_and_entity_timeline():
    db = TestingSessionLocal()
    row = AuditLog(
        entity_type="invoice",
        entity_id=1,
        action="status_change",
        reason_code="data_fix",
        changed_by="auditor",
        changed_at=datetime.now(UTC),
    )
    db.add(row)
    db.commit()
    audit_id = row.id
    db.close()

    client = _client()
    list_res = client.get("/api/v1/audit-logs", headers=_auth())
    assert list_res.status_code == 200
    assert list_res.json()["total"] >= 1
    assert list_res.json()["items"][0]["entityType"] == "invoice"

    detail = client.get(f"/api/v1/audit-logs/{audit_id}", headers=_auth())
    assert detail.status_code == 200
    assert detail.json()["id"] == audit_id

    timeline = client.get("/api/v1/audit-logs/entities/invoice/1", headers=_auth())
    assert timeline.status_code == 200
    assert timeline.json()["total"] >= 1


def test_audit_logs_are_written_for_mutating_operations():
    client = _client()

    product = client.post(
        "/api/v1/products",
        json={
            "sku": "SKU-AUD-1",
            "name": "Audit Product",
            "order_uom": "count",
            "purchase_uom": "count",
            "invoice_uom": "count",
            "pricing_basis_default": "uom_count",
        },
    ).json()

    customer = client.post(
        "/api/v1/customers",
        json={"code": "C-AUD-1", "name": "Audit Customer", "active": True},
    ).json()

    order = client.post(
        "/api/v1/orders",
        json={"order_no": "ORD-AUD-1", "customer_id": customer["id"], "delivery_date": datetime.now(UTC).date().isoformat()},
    ).json()

    invoice = client.post(
        "/api/v1/invoices",
        json={"invoice_no": "INV-AUD-1", "order_id": order["id"], "invoice_date": datetime.now(UTC).date().isoformat()},
    ).json()

    # verify timeline exists for each entity type
    for entity_type, entity_id in [
        ("product", product["id"]),
        ("customer", customer["id"]),
        ("order", order["id"]),
        ("invoice", invoice["id"]),
    ]:
        timeline = client.get(f"/api/v1/audit-logs/entities/{entity_type}/{entity_id}", headers=_auth())
        assert timeline.status_code == 200
        assert timeline.json()["total"] >= 1
