from datetime import datetime

from pydantic import BaseModel, Field


class SupplierProductCreateRequest(BaseModel):
    product_id: int = Field(gt=0)
    priority: int = Field(default=100, ge=1, le=9999)
    is_preferred: bool = False
    note: str | None = Field(default=None, max_length=1000)


class SupplierProductResponse(BaseModel):
    id: int
    supplier_id: int
    product_id: int
    priority: int
    is_preferred: bool
    note: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
