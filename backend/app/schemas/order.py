from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.entities import LineStatus, OrderStatus, PricingBasis


class OrderCreateRequest(BaseModel):
    customer_id: int = Field(gt=0)
    delivery_date: date
    note: str | None = Field(default=None, max_length=1000)


class OrderUpdateRequest(BaseModel):
    customer_id: int | None = Field(default=None, gt=0)
    delivery_date: date | None = None
    note: str | None = Field(default=None, max_length=1000)


class OrderBulkTransitionRequest(BaseModel):
    from_status: OrderStatus
    to_status: OrderStatus


class OrderBulkTransitionResponse(BaseModel):
    order_id: int
    updated_lines: int
    updated_order_status: OrderStatus


class OrderResponse(BaseModel):
    id: int
    order_no: str
    customer_id: int
    order_datetime: datetime
    delivery_date: date
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
    pricing_basis: PricingBasis = PricingBasis.uom_count
    unit_price_uom_count: float | None = Field(default=None, ge=0)
    unit_price_uom_kg: float | None = Field(default=None, ge=0)
    note: str | None = Field(default=None, max_length=1000)


class OrderItemUpdateRequest(BaseModel):
    ordered_qty: float | None = Field(default=None, gt=0)
    order_uom_type: PricingBasis | None = None
    pricing_basis: PricingBasis | None = None
    unit_price_uom_count: float | None = Field(default=None, ge=0)
    unit_price_uom_kg: float | None = Field(default=None, ge=0)
    note: str | None = Field(default=None, max_length=1000)


class OrderItemResponse(BaseModel):
    id: int
    order_id: int
    product_id: int
    ordered_qty: float
    order_uom_type: PricingBasis
    estimated_weight_kg: float | None
    actual_weight_kg: float | None
    pricing_basis: PricingBasis
    unit_price_uom_count: float | None
    unit_price_uom_kg: float | None
    note: str | None
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
