from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.entities import BatchJobStatus


class AllocationRunRequest(BaseModel):
    business_date: date
    idempotency_key: str = Field(min_length=8, max_length=128)
    requested_count: int = Field(default=0, ge=0)


class BatchJobSummary(BaseModel):
    requestedCount: int
    processedCount: int
    succeededCount: int
    failedCount: int
    skippedCount: int
    retryCount: int
    durationMs: int | None
    startedAt: datetime | None
    finishedAt: datetime | None


class BatchJobResponse(BaseModel):
    jobId: int
    jobType: str
    businessDate: date | None
    status: BatchJobStatus
    traceId: str
    requestId: str
    actor: str
    summary: BatchJobSummary
    errors: list[dict] = []


class BatchJobListResponse(BaseModel):
    items: list[BatchJobResponse]
    count: int
