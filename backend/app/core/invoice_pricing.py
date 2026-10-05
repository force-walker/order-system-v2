from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from collections.abc import Iterable

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
    raw = compute_invoice_cost_basis(
        jpy_purchase_unit_cost=jpy_purchase_unit_cost,
        freight_weight=freight_weight,
        settings=settings,
    )
    return money(raw) if raw is not None else None


def compute_invoice_cost_basis(
    *,
    jpy_purchase_unit_cost: Decimal | None,
    freight_weight: Decimal | None,
    settings: SystemSettings,
) -> Decimal | None:
    jp_gross_margin_pct = Decimal(str(settings.jp_gross_margin_pct))
    exchange_rate = Decimal(str(settings.exchange_rate))
    freight_unit_price = Decimal(str(settings.freight_unit_price))
    if freight_weight is None or freight_weight <= 0:
        raise HTTPException(
            status_code=422,
            detail={"code": "FREIGHT_WEIGHT_REQUIRED", "message": "product freight_weight must be greater than 0"},
        )
    if jpy_purchase_unit_cost is None:
        return None

    if jp_gross_margin_pct < 0 or jp_gross_margin_pct >= 100:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "INVALID_SYSTEM_SETTINGS",
                "message": "jp_gross_margin_pct must be between 0 and 100 for draft pricing",
            },
        )

    base_cost_hkd = jpy_purchase_unit_cost / exchange_rate
    japan_adjusted_cost = base_cost_hkd / ((Decimal("100") - jp_gross_margin_pct) / Decimal("100"))
    freight_component = freight_unit_price * freight_weight
    return japan_adjusted_cost + freight_component


def compute_unit_freight_cost(*, freight_weight: Decimal, settings: SystemSettings) -> Decimal:
    return freight_weight * Decimal(str(settings.freight_unit_price))


def compute_weighted_purchase_unit_cost(rows: Iterable[tuple[Decimal, Decimal | None]]) -> Decimal | None:
    values = list(rows)
    if not values or any(cost is None for _, cost in values):
        return None
    total_quantity = sum((quantity for quantity, _ in values), Decimal("0"))
    if total_quantity <= 0:
        return None
    return sum((quantity * cost for quantity, cost in values if cost is not None), Decimal("0")) / total_quantity


def compute_default_sales_unit_price(*, unit_cost_basis: Decimal | None, settings: SystemSettings) -> Decimal | None:
    if unit_cost_basis is None:
        return None
    hk_margin_pct = Decimal(str(settings.hk_gross_margin_pct))
    if hk_margin_pct < 0 or hk_margin_pct >= 100:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "INVALID_SYSTEM_SETTINGS",
                "message": "hk_gross_margin_pct must be between 0 and 100 for draft pricing",
            },
        )
    return money(unit_cost_basis / ((Decimal("100") - hk_margin_pct) / Decimal("100")))


def compute_draft_margin(
    *,
    sales_unit_price: Decimal,
    unit_cost_basis: Decimal | None,
) -> DraftMarginResult:
    if sales_unit_price == 0 or unit_cost_basis is None:
        return DraftMarginResult(gross_margin_pct=None, gross_margin_unavailable=True)

    gross_margin_pct = money(((sales_unit_price - unit_cost_basis) / sales_unit_price) * Decimal("100"))
    return DraftMarginResult(gross_margin_pct=float(gross_margin_pct), gross_margin_unavailable=False)
