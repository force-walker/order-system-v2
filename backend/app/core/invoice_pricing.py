from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.entities import SystemSettings


def money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class DraftMarginResult:
    gross_margin_pct: float | None
    gross_margin_unavailable: bool


def get_system_settings_or_404(db: Session) -> SystemSettings:
    row = db.query(SystemSettings).filter(SystemSettings.id == 1).first()
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "SYSTEM_SETTINGS_NOT_FOUND", "message": "system settings not found"},
        )
    return row


def compute_hkd_purchase_unit_cost(
    *,
    jpy_purchase_unit_cost: Decimal | None,
    freight_weight: Decimal | None,
    settings: SystemSettings,
) -> Decimal | None:
    if jpy_purchase_unit_cost is None:
        return None

    jp_gross_margin_pct = Decimal(str(settings.jp_gross_margin_pct))
    exchange_rate = Decimal(str(settings.exchange_rate))
    freight_unit_price = Decimal(str(settings.freight_unit_price))
    freight_weight_dec = freight_weight if freight_weight is not None else Decimal("0")

    if jp_gross_margin_pct <= 0:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "INVALID_SYSTEM_SETTINGS",
                "message": "jp_gross_margin_pct must be greater than 0 for draft pricing",
            },
        )

    converted = jpy_purchase_unit_cost / jp_gross_margin_pct / exchange_rate
    freight_component = freight_unit_price * freight_weight_dec * freight_weight_dec
    return money(converted + freight_component)


def compute_draft_margin(
    *,
    sales_unit_price: Decimal,
    unit_cost_basis: Decimal | None,
) -> DraftMarginResult:
    if sales_unit_price == 0 or unit_cost_basis is None:
        return DraftMarginResult(gross_margin_pct=None, gross_margin_unavailable=True)

    gross_margin_pct = money(((sales_unit_price - unit_cost_basis) / sales_unit_price) * Decimal("100"))
    return DraftMarginResult(gross_margin_pct=float(gross_margin_pct), gross_margin_unavailable=False)
