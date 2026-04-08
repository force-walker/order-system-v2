from datetime import datetime

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
    name: str
    active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
