import json
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.entities import AuditLog


class AuditAction:
    CREATE = "create"
    UPDATE = "update"
    BULK_TRANSITION = "bulk_transition"
    FINALIZE = "finalize"
    RESET_TO_DRAFT = "reset_to_draft"
    UNLOCK = "unlock"
    OVERRIDE = "override"
    SPLIT_LINE = "split_line"
    BULK_UPSERT_CREATE = "bulk_upsert_create"
    BULK_UPSERT_UPDATE = "bulk_upsert_update"

    ENQUEUE = "enqueue"
    START = "start"
    COMPLETE = "complete"
    CANCEL = "cancel"
    RETRY = "retry"


DEFAULT_AUDIT_ACTOR = "system_api"


def write_audit_log(
    db: Session,
    *,
    entity_type: str,
    entity_id: int,
    action: str,
    actor: str = DEFAULT_AUDIT_ACTOR,
    reason_code: str | None = None,
    before: dict | None = None,
    after: dict | None = None,
    trace_id: str | None = None,
    request_id: str | None = None,
    job_id: str | None = None,
) -> None:
    db.add(
        AuditLog(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            before_json=(json.dumps(before, ensure_ascii=False) if before is not None else None),
            after_json=(json.dumps(after, ensure_ascii=False) if after is not None else None),
            reason_code=reason_code,
            changed_by=actor,
            trace_id=trace_id,
            request_id=request_id,
            job_id=job_id,
            changed_at=datetime.now(UTC),
        )
    )
