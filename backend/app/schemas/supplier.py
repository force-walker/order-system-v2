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


class SupplierCreateRequest(PaymentTermsMixin):
    name: str = Field(min_length=1, max_length=255)
    active: bool = True

    model_config = {"extra": "forbid"}


class SupplierUpdateRequest(PaymentTermsMixin):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    active: bool | None = None


class SupplierResponse(BaseModel):
    id: int
    supplier_code: str
    import_key: str | None
    name: str
    active: bool
    payment_terms_type: PaymentTermsType | None
    payment_terms_days: int | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SupplierImportItem(BaseModel):
    import_key: str | None = Field(default=None, min_length=1, max_length=128)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    active: bool | None = None

    model_config = {"extra": "forbid"}


class SupplierImportRequest(BaseModel):
    items: list[dict[str, Any]] = Field(min_length=1, max_length=2000)

    model_config = {"extra": "forbid"}


class SupplierImportError(BaseModel):
    index: int
    import_key: str | None = None
    action: str
    code: str
    message: str
    supplier_id: int | None = None

    model_config = {"extra": "forbid"}


class SupplierImportResult(BaseModel):
    total: int
    created: int
    updated: int
    skipped: int
    failed: int
    errors: list[SupplierImportError] = Field(default_factory=list)

    model_config = {"extra": "forbid"}
