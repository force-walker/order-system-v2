from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.auth import AuthContext, require_roles
from app.db.session import get_db
from app.models.entities import AuditLog
from app.schemas.audit import AuditActor, AuditLogItem, AuditLogListResponse

router = APIRouter(prefix="/api/v1/audit-logs", tags=["audit"])


def _to_item(r: AuditLog) -> AuditLogItem:
    return AuditLogItem(
        id=r.id,
        occurredAt=r.changed_at,
        actor=AuditActor(id=r.changed_by),
        action=r.action,
        entityType=r.entity_type,
        entityId=r.entity_id,
        reasonCode=r.reason_code,
        before=None,
        after=None,
        traceId=None,
        requestId=None,
        jobId=None,
        source="api",
    )


@router.get("", response_model=AuditLogListResponse)
def list_audit_logs(
    entityType: str | None = Query(default=None),
    entityId: int | None = Query(default=None),
    actorId: str | None = Query(default=None),
    action: str | None = Query(default=None),
    from_ts: datetime | None = Query(default=None, alias="from"),
    to_ts: datetime | None = Query(default=None, alias="to"),
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_roles("admin", "buyer", "order_entry")),
) -> AuditLogListResponse:
    if from_ts and to_ts and from_ts > to_ts:
        raise HTTPException(status_code=422, detail={"code": "VALIDATION_FAILED", "message": "invalid date range"})

    q = db.query(AuditLog)
    if entityType:
        q = q.filter(AuditLog.entity_type == entityType)
    if entityId:
        q = q.filter(AuditLog.entity_id == entityId)
    if actorId:
        q = q.filter(AuditLog.changed_by == actorId)
    if action:
        q = q.filter(AuditLog.action == action)
    if from_ts:
        q = q.filter(AuditLog.changed_at >= from_ts)
    if to_ts:
        q = q.filter(AuditLog.changed_at <= to_ts)

    total = q.count()
    rows = (
        q.order_by(AuditLog.changed_at.desc())
        .offset((page - 1) * pageSize)
        .limit(pageSize)
        .all()
    )
    items = [_to_item(r) for r in rows]
    return AuditLogListResponse(items=items, page=page, pageSize=pageSize, total=total)


@router.get("/{auditLogId}", response_model=AuditLogItem)
def get_audit_log(
    auditLogId: int,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_roles("admin", "buyer", "order_entry")),
) -> AuditLogItem:
    row = db.query(AuditLog).filter(AuditLog.id == auditLogId).first()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "RESOURCE_NOT_FOUND", "message": "audit log not found"})
    return _to_item(row)


@router.get("/entities/{entityType}/{entityId}", response_model=AuditLogListResponse)
def get_entity_timeline(
    entityType: str,
    entityId: int,
    from_ts: datetime | None = Query(default=None, alias="from"),
    to_ts: datetime | None = Query(default=None, alias="to"),
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_roles("admin", "buyer", "order_entry")),
) -> AuditLogListResponse:
    return list_audit_logs(
        entityType=entityType,
        entityId=entityId,
        actorId=None,
        action=None,
        from_ts=from_ts,
        to_ts=to_ts,
        page=page,
        pageSize=pageSize,
        db=db,
        auth=auth,
    )
