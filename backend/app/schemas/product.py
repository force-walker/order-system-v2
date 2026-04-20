from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.entities import PricingBasis


class ProductCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    legacy_code: str | None = Field(default=None, min_length=1, max_length=128)
    category_code: str | None = Field(default=None, min_length=1, max_length=16)
    product_type_code: str | None = Field(default=None, min_length=1, max_length=16)
    name_kana: str | None = Field(default=None, min_length=1, max_length=255)
    name_kana_key: str | None = Field(default=None, min_length=1, max_length=64)
    legacy_unit_code: str | None = Field(default=None, min_length=1, max_length=64)
    pack_size: int | None = Field(default=None, ge=0)
    tax_category_code: str | None = Field(default=None, min_length=1, max_length=16)
    inventory_category_code: str | None = Field(default=None, min_length=1, max_length=16)
    owner_code: str | None = Field(default=None, min_length=1, max_length=32)
    origin_code: str | None = Field(default=None, min_length=1, max_length=32)
    jan_code: str | None = Field(default=None, min_length=1, max_length=32)
    sales_price: float | None = Field(default=None, ge=0)
    sales_price_1: float | None = Field(default=None, ge=0)
    sales_price_2: float | None = Field(default=None, ge=0)
    sales_price_3: float | None = Field(default=None, ge=0)
    sales_price_4: float | None = Field(default=None, ge=0)
    sales_price_5: float | None = Field(default=None, ge=0)
    sales_price_6: float | None = Field(default=None, ge=0)
    purchase_price: float | None = Field(default=None, ge=0)
    inventory_price: float | None = Field(default=None, ge=0)
    list_price: float | None = Field(default=None, ge=0)
    tax_rate_code: str | None = Field(default=None, min_length=1, max_length=16)
    handling_category_code: str | None = Field(default=None, min_length=1, max_length=16)
    name_en: str | None = Field(default=None, min_length=1, max_length=255)
    name_zh_hk: str | None = Field(default=None, min_length=1, max_length=255)
    customs_reference_price: float | None = Field(default=None, ge=0)
    customs_origin_text: str | None = Field(default=None, min_length=1, max_length=255)
    remarks: str | None = None
    chayafuda_flag: bool | None = None
    application_category_code: str | None = Field(default=None, min_length=1, max_length=16)
    order_uom: str = Field(min_length=1, max_length=32)
    purchase_uom: str = Field(min_length=1, max_length=32)
    invoice_uom: str = Field(min_length=1, max_length=32)
    is_catch_weight: bool = False
    weight_capture_required: bool = False
    pricing_basis_default: PricingBasis = PricingBasis.uom_count

    model_config = {"extra": "forbid"}


class ProductUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    legacy_code: str | None = Field(default=None, min_length=1, max_length=128)
    category_code: str | None = Field(default=None, min_length=1, max_length=16)
    product_type_code: str | None = Field(default=None, min_length=1, max_length=16)
    name_kana: str | None = Field(default=None, min_length=1, max_length=255)
    name_kana_key: str | None = Field(default=None, min_length=1, max_length=64)
    legacy_unit_code: str | None = Field(default=None, min_length=1, max_length=64)
    pack_size: int | None = Field(default=None, ge=0)
    tax_category_code: str | None = Field(default=None, min_length=1, max_length=16)
    inventory_category_code: str | None = Field(default=None, min_length=1, max_length=16)
    owner_code: str | None = Field(default=None, min_length=1, max_length=32)
    origin_code: str | None = Field(default=None, min_length=1, max_length=32)
    jan_code: str | None = Field(default=None, min_length=1, max_length=32)
    sales_price: float | None = Field(default=None, ge=0)
    sales_price_1: float | None = Field(default=None, ge=0)
    sales_price_2: float | None = Field(default=None, ge=0)
    sales_price_3: float | None = Field(default=None, ge=0)
    sales_price_4: float | None = Field(default=None, ge=0)
    sales_price_5: float | None = Field(default=None, ge=0)
    sales_price_6: float | None = Field(default=None, ge=0)
    purchase_price: float | None = Field(default=None, ge=0)
    inventory_price: float | None = Field(default=None, ge=0)
    list_price: float | None = Field(default=None, ge=0)
    tax_rate_code: str | None = Field(default=None, min_length=1, max_length=16)
    handling_category_code: str | None = Field(default=None, min_length=1, max_length=16)
    name_en: str | None = Field(default=None, min_length=1, max_length=255)
    name_zh_hk: str | None = Field(default=None, min_length=1, max_length=255)
    customs_reference_price: float | None = Field(default=None, ge=0)
    customs_origin_text: str | None = Field(default=None, min_length=1, max_length=255)
    remarks: str | None = None
    chayafuda_flag: bool | None = None
    application_category_code: str | None = Field(default=None, min_length=1, max_length=16)
    order_uom: str | None = Field(default=None, min_length=1, max_length=32)
    purchase_uom: str | None = Field(default=None, min_length=1, max_length=32)
    invoice_uom: str | None = Field(default=None, min_length=1, max_length=32)
    is_catch_weight: bool | None = None
    weight_capture_required: bool | None = None
    active: bool | None = None


class ProductResponse(BaseModel):
    id: int
    sku: str
    legacy_code: str | None
    category_code: str | None
    product_type_code: str | None
    name_kana: str | None
    name_kana_key: str | None
    legacy_unit_code: str | None
    pack_size: int | None
    tax_category_code: str | None
    inventory_category_code: str | None
    owner_code: str | None
    origin_code: str | None
    jan_code: str | None
    sales_price: float | None
    sales_price_1: float | None
    sales_price_2: float | None
    sales_price_3: float | None
    sales_price_4: float | None
    sales_price_5: float | None
    sales_price_6: float | None
    purchase_price: float | None
    inventory_price: float | None
    list_price: float | None
    tax_rate_code: str | None
    handling_category_code: str | None
    name_en: str | None
    name_zh_hk: str | None
    customs_reference_price: float | None
    customs_origin_text: str | None
    remarks: str | None
    chayafuda_flag: bool | None
    application_category_code: str | None
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


class ProductBulkCreateItem(BaseModel):
    sku: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    legacy_code: str | None = Field(default=None, min_length=1, max_length=128)
    legacy_unit_code: str | None = Field(default=None, min_length=1, max_length=64)
    order_uom: str = Field(min_length=1, max_length=32)
    purchase_uom: str = Field(min_length=1, max_length=32)
    invoice_uom: str = Field(min_length=1, max_length=32)
    is_catch_weight: bool = False
    weight_capture_required: bool = False
    pricing_basis_default: PricingBasis = PricingBasis.uom_count


class ProductBulkCreateRequest(BaseModel):
    items: list[ProductBulkCreateItem] = Field(min_length=1, max_length=500)


class ProductBulkUpdateItem(BaseModel):
    id: int = Field(gt=0)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    legacy_code: str | None = Field(default=None, min_length=1, max_length=128)
    legacy_unit_code: str | None = Field(default=None, min_length=1, max_length=64)
    order_uom: str | None = Field(default=None, min_length=1, max_length=32)
    purchase_uom: str | None = Field(default=None, min_length=1, max_length=32)
    invoice_uom: str | None = Field(default=None, min_length=1, max_length=32)
    is_catch_weight: bool | None = None
    weight_capture_required: bool | None = None
    active: bool | None = None


class ProductBulkUpdateRequest(BaseModel):
    items: list[ProductBulkUpdateItem] = Field(min_length=1, max_length=500)


class ProductBulkUpsertRequest(BaseModel):
    items: list[ProductBulkCreateItem] = Field(min_length=1, max_length=500)


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


class ProductImportItem(BaseModel):
    legacy_code: str | None = Field(default=None, min_length=1, max_length=128)
    category_code: str | None = Field(default=None, min_length=1, max_length=16)
    product_type_code: str | None = Field(default=None, min_length=1, max_length=16)
    name: str = Field(min_length=1, max_length=255)
    name_kana: str | None = Field(default=None, min_length=1, max_length=255)
    name_kana_key: str | None = Field(default=None, min_length=1, max_length=64)
    legacy_unit_code: str | None = Field(default=None, min_length=1, max_length=64)
    pack_size: int | None = Field(default=None, ge=0)
    tax_category_code: str | None = Field(default=None, min_length=1, max_length=16)
    inventory_category_code: str | None = Field(default=None, min_length=1, max_length=16)
    owner_code: str | None = Field(default=None, min_length=1, max_length=32)
    origin_code: str | None = Field(default=None, min_length=1, max_length=32)
    jan_code: str | None = Field(default=None, min_length=1, max_length=32)
    sales_price: float | None = Field(default=None, ge=0)
    sales_price_1: float | None = Field(default=None, ge=0)
    sales_price_2: float | None = Field(default=None, ge=0)
    sales_price_3: float | None = Field(default=None, ge=0)
    sales_price_4: float | None = Field(default=None, ge=0)
    sales_price_5: float | None = Field(default=None, ge=0)
    sales_price_6: float | None = Field(default=None, ge=0)
    purchase_price: float | None = Field(default=None, ge=0)
    inventory_price: float | None = Field(default=None, ge=0)
    list_price: float | None = Field(default=None, ge=0)
    tax_rate_code: str | None = Field(default=None, min_length=1, max_length=16)
    handling_category_code: str | None = Field(default=None, min_length=1, max_length=16)
    name_en: str | None = Field(default=None, min_length=1, max_length=255)
    name_zh_hk: str | None = Field(default=None, min_length=1, max_length=255)
    customs_reference_price: float | None = Field(default=None, ge=0)
    customs_origin_text: str | None = Field(default=None, min_length=1, max_length=255)
    remarks: str | None = None
    chayafuda_flag: bool | None = None
    application_category_code: str | None = Field(default=None, min_length=1, max_length=16)
    order_uom: str = Field(min_length=1, max_length=32)
    purchase_uom: str = Field(min_length=1, max_length=32)
    invoice_uom: str = Field(min_length=1, max_length=32)
    is_catch_weight: bool = False
    weight_capture_required: bool = False
    pricing_basis_default: PricingBasis = PricingBasis.uom_count
    active: bool = True


class ProductImportRequest(BaseModel):
    items: list[dict[str, Any]] = Field(min_length=1, max_length=2000)


class ProductImportResult(BaseModel):
    total: int
    created: int
    updated: int
    skipped: int
    failed: int
    errors: list[BulkOperationError] = Field(default_factory=list)
