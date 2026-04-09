from datetime import datetime

from pydantic import BaseModel, Field


class SupplierProductCreateRequest(BaseModel):
    product_id: int = Field(gt=0)
    priority: int = Field(default=100, ge=1, le=9999)
    is_preferred: bool = False
    default_unit_cost: float | None = Field(default=None, ge=0)
    lead_time_days: int | None = Field(default=None, ge=0)
    note: str | None = Field(default=None, max_length=1000)


class SupplierProductMappingCreateRequest(BaseModel):
    supplier_id: int = Field(gt=0)
    product_id: int = Field(gt=0)
    priority: int = Field(default=100, ge=1, le=9999)
    is_preferred: bool = False
    default_unit_cost: float | None = Field(default=None, ge=0)
    lead_time_days: int | None = Field(default=None, ge=0)
    note: str | None = Field(default=None, max_length=1000)


class SupplierProductUpdateRequest(BaseModel):
    priority: int | None = Field(default=None, ge=1, le=9999)
    is_preferred: bool | None = None
    default_unit_cost: float | None = Field(default=None, ge=0)
    lead_time_days: int | None = Field(default=None, ge=0)
    note: str | None = Field(default=None, max_length=1000)


class SupplierProductResponse(BaseModel):
    id: int
    supplier_id: int
    product_id: int
    priority: int
    is_preferred: bool
    default_unit_cost: float | None
    lead_time_days: int | None
    note: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
