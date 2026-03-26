from datetime import datetime

from pydantic import BaseModel


class AuditActor(BaseModel):
    id: str
    name: str | None = None
    role: str | None = None


class AuditLogItem(BaseModel):
    id: int
    occurredAt: datetime
    actor: AuditActor
    action: str
    entityType: str
    entityId: int
    reasonCode: str | None = None
    before: dict | None = None
    after: dict | None = None
    traceId: str | None = None
    requestId: str | None = None
    jobId: str | None = None
    source: str = "api"


class AuditLogListResponse(BaseModel):
    items: list[AuditLogItem]
    page: int
    pageSize: int
    total: int
