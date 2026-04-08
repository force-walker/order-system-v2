from datetime import datetime

from pydantic import BaseModel, Field

from app.models.entities import PricingBasis


class ProductCreateRequest(BaseModel):
    sku: str | None = Field(default=None, min_length=1, max_length=64)
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


class ProductBulkCreateRequest(BaseModel):
    items: list[ProductCreateRequest] = Field(min_length=1, max_length=500)


class ProductBulkUpdateItem(BaseModel):
    id: int = Field(gt=0)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    order_uom: str | None = Field(default=None, min_length=1, max_length=32)
    purchase_uom: str | None = Field(default=None, min_length=1, max_length=32)
    invoice_uom: str | None = Field(default=None, min_length=1, max_length=32)
    is_catch_weight: bool | None = None
    weight_capture_required: bool | None = None
    active: bool | None = None


class ProductBulkUpdateRequest(BaseModel):
    items: list[ProductBulkUpdateItem] = Field(min_length=1, max_length=500)


class ProductBulkUpsertRequest(BaseModel):
    items: list[ProductCreateRequest] = Field(min_length=1, max_length=500)


class ProductBulkDeleteRequest(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=500)


class BulkOperationError(BaseModel):
    index: int
    itemRef: str | None = None
    code: str
    message: str


class BulkOperationSummary(BaseModel):
    total: int
    success: int
    failed: int


class ProductBulkOperationResponse(BaseModel):
    summary: BulkOperationSummary
    errors: list[BulkOperationError] = Field(default_factory=list)
