from datetime import UTC, date, datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.auth import issue_tokens
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.entities import BatchJob, BatchJobStatus


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


def _auth() -> dict[str, str]:
    access, _, _ = issue_tokens("tester", "admin")
    return {"Authorization": f"Bearer {access}"}


def test_batch_enqueue_status_list_and_idempotency():
    client = _client()
    payload = {
        "business_date": str(date.today()),
        "idempotency_key": f"idem-{datetime.now(UTC).timestamp()}",
        "requested_count": 10,
    }
    enq = client.post("/api/v1/allocations/runs", json=payload, headers=_auth())
    assert enq.status_code == 202
    job_id = enq.json()["jobId"]

    # same idempotency key should return same job
    idem = client.post("/api/v1/allocations/runs", json=payload, headers=_auth())
    assert idem.status_code == 202
    assert idem.json()["jobId"] == job_id

    status1 = client.get(f"/api/v1/batch/jobs/{job_id}", headers=_auth())
    assert status1.status_code == 200
    assert status1.json()["status"] == "running"

    status2 = client.get(f"/api/v1/batch/jobs/{job_id}", headers=_auth())
    assert status2.status_code == 200
    assert status2.json()["status"] == "succeeded"

    listed = client.get("/api/v1/batch/jobs", headers=_auth())
    assert listed.status_code == 200
    assert listed.json()["count"] >= 1


def test_batch_cancel_queued_success_then_conflict():
    client = _client()
    payload = {
        "business_date": str(date.today()),
        "idempotency_key": f"idem-cancel-{datetime.now(UTC).timestamp()}",
        "requested_count": 1,
    }
    enq = client.post("/api/v1/allocations/runs", json=payload, headers=_auth())
    job_id = enq.json()["jobId"]

    cancel_ok = client.post(f"/api/v1/batch/jobs/{job_id}/cancel", headers=_auth())
    assert cancel_ok.status_code == 200
    assert cancel_ok.json()["status"] == "cancelled"

    cancel_ng = client.post(f"/api/v1/batch/jobs/{job_id}/cancel", headers=_auth())
    assert cancel_ng.status_code == 409
    assert cancel_ng.json()["detail"]["code"] == "RETRY_NOT_ALLOWED"


def test_batch_retry_failed_job():
    client = _client()
    payload = {
        "business_date": str(date.today()),
        "idempotency_key": f"idem-retry-{datetime.now(UTC).timestamp()}",
        "requested_count": 2,
    }
    enq = client.post("/api/v1/allocations/runs", json=payload, headers=_auth())
    job_id = enq.json()["jobId"]

    # force failed state
    db = TestingSessionLocal()
    job = db.query(BatchJob).filter(BatchJob.id == job_id).first()
    job.status = BatchJobStatus.failed
    job.failed_count = 2
    job.retry_count = 0
    db.commit()
    db.close()

    retry = client.post(f"/api/v1/batch/jobs/{job_id}/retry", headers=_auth())
    assert retry.status_code == 200
    assert retry.json()["status"] == "queued"
    assert retry.json()["summary"]["retryCount"] == 1
