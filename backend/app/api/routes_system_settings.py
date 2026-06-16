from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.audit import AuditAction, write_audit_log
from app.db.session import get_db
from app.models.entities import SystemSettings
from app.schemas.common import ApiErrorResponse
from app.schemas.system_settings import SystemSettingsResponse, SystemSettingsUpdateRequest

router = APIRouter(prefix="/api/v1/system-settings", tags=["system-settings"])

SYSTEM_SETTINGS_ERROR_RESPONSES = {
    404: {"model": ApiErrorResponse, "description": "Not Found"},
    422: {"model": ApiErrorResponse, "description": "Validation Error"},
}


def _get_singleton(db: Session) -> SystemSettings:
    row = db.query(SystemSettings).filter(SystemSettings.id == 1).first()
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "SYSTEM_SETTINGS_NOT_FOUND", "message": "system settings not found"},
        )
    return row


def _audit_snapshot(row: SystemSettings) -> dict[str, float]:
    return {
        "exchange_rate": float(Decimal(str(row.exchange_rate))),
        "jp_gross_margin_pct": float(Decimal(str(row.jp_gross_margin_pct))),
        "hk_gross_margin_pct": float(Decimal(str(row.hk_gross_margin_pct))),
        "freight_unit_price": float(Decimal(str(row.freight_unit_price))),
    }


@router.get("", response_model=SystemSettingsResponse, responses=SYSTEM_SETTINGS_ERROR_RESPONSES)
def get_system_settings(db: Session = Depends(get_db)) -> SystemSettingsResponse:
    return SystemSettingsResponse.model_validate(_get_singleton(db))


@router.put("", response_model=SystemSettingsResponse, responses=SYSTEM_SETTINGS_ERROR_RESPONSES)
def upsert_system_settings(
    payload: SystemSettingsUpdateRequest,
    db: Session = Depends(get_db),
) -> SystemSettingsResponse:
    row = _get_singleton(db)
    before = _audit_snapshot(row)

    row.exchange_rate = payload.exchange_rate
    row.jp_gross_margin_pct = payload.jp_gross_margin_pct
    row.hk_gross_margin_pct = payload.hk_gross_margin_pct
    row.freight_unit_price = payload.freight_unit_price

    db.flush()
    write_audit_log(
        db,
        entity_type="system_settings",
        entity_id=row.id,
        action=AuditAction.UPDATE,
        before=before,
        after=_audit_snapshot(row),
    )
    db.commit()
    db.refresh(row)
    return SystemSettingsResponse.model_validate(row)
