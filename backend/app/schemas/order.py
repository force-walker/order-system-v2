from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.entities import LineStatus, OrderStatus, PricingBasis, StockoutPolicy


class OrderCreateRequest(BaseModel):
    customer_id: int = Field(gt=0)
    delivery_date: date | None = None
    shipped_date: date | None = None
    note: str | None = Field(default=None, max_length=1000)


class OrderUpdateRequest(BaseModel):
    customer_id: int | None = Field(default=None, gt=0)
    delivery_date: date | None = None
    shipped_date: date | None = None
    note: str | None = Field(default=None, max_length=1000)


class OrderBulkTransitionRequest(BaseModel):
    from_status: OrderStatus
    to_status: OrderStatus


class OrderBulkTransitionResponse(BaseModel):
    order_id: int
    updated_lines: int
    updated_order_status: OrderStatus


class OrderBulkCancelRequest(BaseModel):
    order_ids: list[int] = Field(min_length=1, max_length=500)
    cancel_reason_code: str = Field(min_length=1, max_length=64)
    note: str | None = Field(default=None, max_length=1000)


class OrderBulkCancelError(BaseModel):
    order_id: int
    code: str
    message: str


class OrderBulkCancelResponse(BaseModel):
    total: int
    succeeded: int
    failed: int
    errors: list[OrderBulkCancelError] = Field(default_factory=list)


class OrderResponse(BaseModel):
    id: int
    order_no: str
    customer_id: int
    order_datetime: datetime
    delivery_date: date
    shipped_date: date | None
    status: OrderStatus
    note: str | None
    created_by: str
    updated_by: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class OrderItemCreateRequest(BaseModel):
    product_id: int = Field(gt=0)
    ordered_qty: float = Field(gt=0)
    order_uom_type: PricingBasis
    estimated_weight_kg: float | None = Field(default=None, gt=0)
    target_price: float | None = Field(default=None, ge=0)
    price_ceiling: float | None = Field(default=None, ge=0)
    stockout_policy: StockoutPolicy | None = None
    pricing_basis: PricingBasis = PricingBasis.uom_count
    unit_price_uom_count: float | None = Field(default=None, ge=0)
    unit_price_uom_kg: float | None = Field(default=None, ge=0)
    note: str | None = Field(default=None, max_length=1000)
    comment: str | None = Field(default=None, max_length=1000)


class OrderItemUpdateRequest(BaseModel):
    ordered_qty: float | None = Field(default=None, gt=0)
    order_uom_type: PricingBasis | None = None
    estimated_weight_kg: float | None = Field(default=None, gt=0)
    target_price: float | None = Field(default=None, ge=0)
    price_ceiling: float | None = Field(default=None, ge=0)
    stockout_policy: StockoutPolicy | None = None
    pricing_basis: PricingBasis | None = None
    unit_price_uom_count: float | None = Field(default=None, ge=0)
    unit_price_uom_kg: float | None = Field(default=None, ge=0)
    note: str | None = Field(default=None, max_length=1000)
    comment: str | None = Field(default=None, max_length=1000)


class OrderItemResponse(BaseModel):
    id: int
    order_id: int
    product_id: int
    ordered_qty: float
    order_uom_type: PricingBasis
    estimated_weight_kg: float | None
    actual_weight_kg: float | None
    target_price: float | None
    price_ceiling: float | None
    stockout_policy: StockoutPolicy | None
    pricing_basis: PricingBasis
    unit_price_uom_count: float | None
    unit_price_uom_kg: float | None
    note: str | None
    comment: str | None
    line_status: LineStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class OrderItemsBulkCreateRequest(BaseModel):
    items: list[OrderItemCreateRequest] = Field(min_length=1, max_length=500)


class OrderItemsBulkCreateResponse(BaseModel):
    total: int
    success: int
    failed: int
    errors: list[dict] = Field(default_factory=list)
