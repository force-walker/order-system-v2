from datetime import datetime

from pydantic import BaseModel, Field

from app.models.entities import PricingBasis


class ProductCreateRequest(BaseModel):
    sku: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    order_uom: str = Field(min_length=1, max_length=32)
    purchase_uom: str = Field(min_length=1, max_length=32)
    invoice_uom: str = Field(min_length=1, max_length=32)
    is_catch_weight: bool = False
    weight_capture_required: bool = False
    pricing_basis_default: PricingBasis = PricingBasis.uom_count


class ProductUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    order_uom: str | None = Field(default=None, min_length=1, max_length=32)
    purchase_uom: str | None = Field(default=None, min_length=1, max_length=32)
    invoice_uom: str | None = Field(default=None, min_length=1, max_length=32)
    is_catch_weight: bool | None = None
    weight_capture_required: bool | None = None
    active: bool | None = None


class ProductResponse(BaseModel):
    id: int
    sku: str
    name: str
    order_uom: str
    purchase_uom: str
    invoice_uom: str
    is_catch_weight: bool
    weight_capture_required: bool
    pricing_basis_default: PricingBasis
    active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
