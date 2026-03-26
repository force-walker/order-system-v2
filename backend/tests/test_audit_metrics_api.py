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
