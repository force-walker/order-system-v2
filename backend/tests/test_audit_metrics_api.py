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


def test_metrics_endpoint():
    client = _client()
    res = client.get("/api/v1/metrics")
    assert res.status_code == 200
    assert "order_system_v2_api_requests_total" in res.text


def test_audit_logs_list():
    db = TestingSessionLocal()
    db.add(
        AuditLog(
            entity_type="invoice",
            entity_id=1,
            action="status_change",
            reason_code="data_fix",
            changed_by="auditor",
            changed_at=datetime.now(UTC),
        )
    )
    db.commit()
    db.close()

    client = _client()
    res = client.get("/api/v1/audit-logs", headers=_auth())
    assert res.status_code == 200
    assert res.json()["count"] >= 1
    assert res.json()["items"][0]["entity_type"] == "invoice"
