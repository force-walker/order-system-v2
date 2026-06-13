from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SupplierCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    active: bool = True

    model_config = {"extra": "forbid"}


class SupplierUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    active: bool | None = None


class SupplierResponse(BaseModel):
    id: int
    supplier_code: str
    import_key: str | None
    name: str
    active: bool
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
