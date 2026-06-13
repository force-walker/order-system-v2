from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CustomerCreateRequest(BaseModel):
    region: str | None = Field(default=None, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    active: bool = True

    model_config = {"extra": "forbid"}


class CustomerUpdateRequest(BaseModel):
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
