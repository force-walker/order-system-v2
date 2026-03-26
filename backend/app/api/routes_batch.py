import json
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.auth import AuthContext, require_roles
from app.db.session import get_db
from app.models.entities import AuditLog, BatchJob, BatchJobStatus
from app.schemas.batch import AllocationRunRequest, BatchJobListResponse, BatchJobResponse, BatchJobSummary

router = APIRouter(prefix="/api/v1", tags=["batch"])


def _audit(db: Session, *, entity_id: int, action: str, actor: str, reason_code: str | None = None) -> None:
    db.add(
        AuditLog(
            entity_type="batch_job",
            entity_id=entity_id,
            action=action,
            reason_code=reason_code,
            changed_by=actor,
            changed_at=datetime.now(UTC),
        )
    )


def _to_response(job: BatchJob) -> BatchJobResponse:
    duration_ms = None
    if job.started_at and job.finished_at:
        duration_ms = int((job.finished_at - job.started_at).total_seconds() * 1000)

    errors = []
    if job.errors_json:
        try:
            errors = json.loads(job.errors_json)
        except Exception:
            errors = [{"message": job.errors_json}]

    return BatchJobResponse(
        jobId=job.id,
        jobType=job.job_type,
        businessDate=job.business_date,
        status=job.status,
        traceId=job.trace_id,
        requestId=job.request_id,
        actor=job.actor,
        summary=BatchJobSummary(
            requestedCount=job.requested_count,
            processedCount=job.processed_count,
            succeededCount=job.succeeded_count,
            failedCount=job.failed_count,
            skippedCount=job.skipped_count,
            retryCount=job.retry_count,
            durationMs=duration_ms,
            startedAt=job.started_at,
            finishedAt=job.finished_at,
        ),
        errors=errors,
    )


@router.post("/allocations/runs", response_model=BatchJobResponse, status_code=202)
def enqueue_allocation_run(
    payload: AllocationRunRequest,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_roles("admin", "buyer")),
    x_request_id: str | None = Header(default=None),
) -> BatchJobResponse:
    # idempotency
    idem = db.query(BatchJob).filter(BatchJob.idempotency_key == payload.idempotency_key).first()
    if idem is not None:
        return _to_response(idem)

    running = (
        db.query(BatchJob)
        .filter(
            BatchJob.job_type == "allocation_run",
            BatchJob.business_date == payload.business_date,
            BatchJob.status.in_([BatchJobStatus.queued, BatchJobStatus.running]),
        )
        .first()
    )
    if running is not None:
        raise HTTPException(status_code=409, detail={"code": "JOB_ALREADY_RUNNING", "message": "job already running"})

    job = BatchJob(
        job_type="allocation_run",
        business_date=payload.business_date,
        idempotency_key=payload.idempotency_key,
        trace_id=uuid4().hex,
        request_id=x_request_id or uuid4().hex,
        actor=auth.user_id,
        status=BatchJobStatus.queued,
        max_retries=1,
        retry_count=0,
        requested_count=payload.requested_count,
        processed_count=0,
        succeeded_count=0,
        failed_count=0,
        skipped_count=0,
        errors_json="[]",
        started_at=None,
        finished_at=None,
    )
    db.add(job)
    db.flush()
    _audit(db, entity_id=job.id, action="enqueue", actor=auth.user_id)
    db.commit()
    db.refresh(job)
    return _to_response(job)


@router.get("/batch/jobs/{job_id}", response_model=BatchJobResponse)
def get_batch_job(job_id: int, db: Session = Depends(get_db), auth: AuthContext = Depends(require_roles("admin", "buyer", "order_entry"))) -> BatchJobResponse:
    job = db.query(BatchJob).filter(BatchJob.id == job_id).first()
    if job is None:
        raise HTTPException(status_code=404, detail={"code": "RESOURCE_NOT_FOUND", "message": "batch job not found"})

    now = datetime.now(UTC)
    # lightweight async simulation for MVP: queued -> running -> succeeded
    if job.status == BatchJobStatus.queued:
        job.status = BatchJobStatus.running
        job.started_at = now
        _audit(db, entity_id=job.id, action="start", actor=auth.user_id)
        db.commit()
        db.refresh(job)
    elif job.status == BatchJobStatus.running:
        job.status = BatchJobStatus.succeeded
        job.processed_count = job.requested_count
        job.succeeded_count = job.requested_count
        job.failed_count = 0
        job.skipped_count = 0
        job.finished_at = now
        _audit(db, entity_id=job.id, action="complete", actor=auth.user_id)
        db.commit()
        db.refresh(job)

    return _to_response(job)


@router.get("/batch/jobs", response_model=BatchJobListResponse)
def list_batch_jobs(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_roles("admin", "buyer", "order_entry")),
    job_type: str | None = Query(default=None),
    status: BatchJobStatus | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> BatchJobListResponse:
    q = db.query(BatchJob)
    if job_type:
        q = q.filter(BatchJob.job_type == job_type)
    if status:
        q = q.filter(BatchJob.status == status)
    rows = q.order_by(BatchJob.id.desc()).limit(limit).all()
    items = [_to_response(r) for r in rows]
    return BatchJobListResponse(items=items, count=len(items))


@router.post("/batch/jobs/{job_id}/cancel", response_model=BatchJobResponse)
def cancel_batch_job(job_id: int, db: Session = Depends(get_db), auth: AuthContext = Depends(require_roles("admin", "buyer"))) -> BatchJobResponse:
    job = db.query(BatchJob).filter(BatchJob.id == job_id).first()
    if job is None:
        raise HTTPException(status_code=404, detail={"code": "RESOURCE_NOT_FOUND", "message": "batch job not found"})
    if job.status in [BatchJobStatus.succeeded, BatchJobStatus.failed, BatchJobStatus.cancelled]:
        raise HTTPException(status_code=409, detail={"code": "RETRY_NOT_ALLOWED", "message": "job already finished"})

    now = datetime.now(UTC)
    job.status = BatchJobStatus.cancelled
    job.finished_at = now
    _audit(db, entity_id=job.id, action="cancel", actor=auth.user_id, reason_code="user_cancel")
    db.commit()
    db.refresh(job)
    return _to_response(job)


@router.post("/batch/jobs/{job_id}/retry", response_model=BatchJobResponse)
def retry_batch_job(
    job_id: int,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_roles("admin", "buyer")),
) -> BatchJobResponse:
    job = db.query(BatchJob).filter(BatchJob.id == job_id).first()
    if job is None:
        raise HTTPException(status_code=404, detail={"code": "RESOURCE_NOT_FOUND", "message": "batch job not found"})
    if job.status != BatchJobStatus.failed:
        raise HTTPException(status_code=409, detail={"code": "RETRY_NOT_ALLOWED", "message": "retry allowed only for failed jobs"})
    if job.retry_count >= job.max_retries:
        raise HTTPException(status_code=409, detail={"code": "RETRY_LIMIT_EXCEEDED", "message": "retry limit exceeded"})

    running = (
        db.query(BatchJob)
        .filter(
            BatchJob.job_type == job.job_type,
            BatchJob.business_date == job.business_date,
            BatchJob.status.in_([BatchJobStatus.queued, BatchJobStatus.running]),
        )
        .first()
    )
    if running is not None:
        raise HTTPException(status_code=409, detail={"code": "JOB_ALREADY_RUNNING", "message": "job already running"})

    job.status = BatchJobStatus.queued
    job.retry_count += 1
    job.started_at = None
    job.finished_at = None
    job.processed_count = 0
    job.succeeded_count = 0
    job.failed_count = 0
    job.skipped_count = 0
    job.errors_json = "[]"
    _audit(db, entity_id=job.id, action="retry", actor=auth.user_id, reason_code="manual_retry")
    db.commit()
    db.refresh(job)
    return _to_response(job)
