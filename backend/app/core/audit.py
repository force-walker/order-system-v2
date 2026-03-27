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
) -> None:
    db.add(
        AuditLog(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            reason_code=reason_code,
            changed_by=actor,
            changed_at=datetime.now(UTC),
        )
    )
