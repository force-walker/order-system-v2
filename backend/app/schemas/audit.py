from datetime import datetime

from pydantic import BaseModel


class AuditLogItem(BaseModel):
    id: int
    entity_type: str
    entity_id: int
    action: str
    reason_code: str | None
    changed_by: str
    changed_at: datetime


class AuditLogListResponse(BaseModel):
    items: list[AuditLogItem]
    count: int
