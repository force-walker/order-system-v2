from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator
from app.models.entities import PaymentTermsType


class PaymentTermsMixin(BaseModel):
    payment_terms_type: PaymentTermsType | None = None
    payment_terms_days: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_payment_terms(self):
        if self.payment_terms_type == PaymentTermsType.days_after_issue and self.payment_terms_days is None:
            raise ValueError("payment_terms_days is required for days_after_issue")
        if self.payment_terms_type not in (None, PaymentTermsType.days_after_issue):
            self.payment_terms_days = None
        return self


class CustomerCreateRequest(PaymentTermsMixin):
    region: str | None = Field(default=None, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    active: bool = True

    model_config = {"extra": "forbid"}


class CustomerUpdateRequest(PaymentTermsMixin):
    region: str | None = Field(default=None, max_length=64)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    active: bool | None = None


class CustomerResponse(BaseModel):
    id: int
    customer_code: str
    import_key: str | None
    region: str | None
    name: str
    active: bool
    payment_terms_type: PaymentTermsType | None
    payment_terms_days: int | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CustomerImportItem(BaseModel):
    import_key: str | None = Field(default=None, min_length=1, max_length=128)
    region: str | None = Field(default=None, min_length=1, max_length=64)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    active: bool | None = None

    model_config = {"extra": "forbid"}


class CustomerImportRequest(BaseModel):
    items: list[dict[str, Any]] = Field(min_length=1, max_length=2000)

    model_config = {"extra": "forbid"}


class CustomerImportError(BaseModel):
    index: int
    import_key: str | None = None
    action: str
    code: str
    message: str
    customer_id: int | None = None

    model_config = {"extra": "forbid"}


class CustomerImportResult(BaseModel):
    total: int
    created: int
    updated: int
    skipped: int
    failed: int
    errors: list[CustomerImportError] = Field(default_factory=list)

    model_config = {"extra": "forbid"}
