from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, computed_field, model_validator


class SystemSettingsUpdateRequest(BaseModel):
    exchange_rate: Decimal = Field(gt=Decimal("0"))
    jp_gross_margin_pct: Decimal | None = Field(default=None, ge=Decimal("0"))
    jp_gross_margin_rate: Decimal | None = Field(default=None, ge=Decimal("0"))
    hk_gross_margin_pct: Decimal = Field(ge=Decimal("0"))
    freight_unit_price: Decimal = Field(ge=Decimal("0"))

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def normalize_margin_aliases(self) -> "SystemSettingsUpdateRequest":
        pct = self.jp_gross_margin_pct
        rate = self.jp_gross_margin_rate
        if pct is None and rate is None:
            raise ValueError("jp_gross_margin_pct or jp_gross_margin_rate is required")
        if pct is not None and rate is not None and pct != rate:
            raise ValueError("jp_gross_margin_pct and jp_gross_margin_rate must match when both are provided")

        normalized = pct if pct is not None else rate
        self.jp_gross_margin_pct = normalized
        self.jp_gross_margin_rate = normalized
        return self


class SystemSettingsResponse(BaseModel):
    exchange_rate: Decimal
    jp_gross_margin_pct: Decimal
    hk_gross_margin_pct: Decimal
    freight_unit_price: Decimal
    updated_at: datetime

    model_config = {"from_attributes": True}

    @computed_field
    @property
    def jp_gross_margin_rate(self) -> Decimal:
        return self.jp_gross_margin_pct
