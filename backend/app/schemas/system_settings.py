from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class SystemSettingsUpdateRequest(BaseModel):
    exchange_rate: Decimal = Field(gt=Decimal("0"))
    jp_gross_margin_pct: Decimal = Field(ge=Decimal("0"))
    hk_gross_margin_pct: Decimal = Field(ge=Decimal("0"))
    freight_unit_price: Decimal = Field(ge=Decimal("0"))

    model_config = {"extra": "forbid"}


class SystemSettingsResponse(BaseModel):
    exchange_rate: Decimal
    jp_gross_margin_pct: Decimal
    hk_gross_margin_pct: Decimal
    freight_unit_price: Decimal
    updated_at: datetime

    model_config = {"from_attributes": True}
