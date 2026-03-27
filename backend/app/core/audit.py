from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.entities import AuditLog


def write_audit_log(
    db: Session,
    *,
    entity_type: str,
    entity_id: int,
    action: str,
    actor: str = "system",
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
