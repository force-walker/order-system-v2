from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth import AuthContext, require_roles
from app.db.session import get_db
from app.models.entities import AuditLog
from app.schemas.audit import AuditLogItem, AuditLogListResponse

router = APIRouter(prefix="/api/v1/audit-logs", tags=["audit"])


@router.get("", response_model=AuditLogListResponse)
def list_audit_logs(
    entity_type: str | None = Query(default=None),
    entity_id: int | None = Query(default=None),
    changed_by: str | None = Query(default=None),
    from_ts: datetime | None = Query(default=None),
    to_ts: datetime | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_roles("admin", "buyer", "order_entry")),
) -> AuditLogListResponse:
    q = db.query(AuditLog)
    if entity_type:
        q = q.filter(AuditLog.entity_type == entity_type)
    if entity_id:
        q = q.filter(AuditLog.entity_id == entity_id)
    if changed_by:
        q = q.filter(AuditLog.changed_by == changed_by)
    if from_ts:
        q = q.filter(AuditLog.changed_at >= from_ts)
    if to_ts:
        q = q.filter(AuditLog.changed_at <= to_ts)

    rows = q.order_by(AuditLog.changed_at.desc()).limit(limit).all()
    items = [
        AuditLogItem(
            id=r.id,
            entity_type=r.entity_type,
            entity_id=r.entity_id,
            action=r.action,
            reason_code=r.reason_code,
            changed_by=r.changed_by,
            changed_at=r.changed_at,
        )
        for r in rows
    ]
    return AuditLogListResponse(items=items, count=len(items))
