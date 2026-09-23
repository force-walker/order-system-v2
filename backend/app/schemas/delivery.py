from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator


class DeliveryBuildRequest(BaseModel):
    order_id: str | int

    @field_validator("order_id")
    @classmethod
    def validate_order_id(cls, value: str | int) -> str | int:
        if isinstance(value, int):
            if value <= 0:
                raise ValueError("order_id must be positive")
            return value
        if value.isdigit() and int(value) <= 0:
            raise ValueError("order_id must be positive")
        if not value:
            raise ValueError("order_id is required")
        return value


class DeliveryResponse(BaseModel):
    id: str
    uuid: str
    document_seq: int | None = Field(default=None, description="Immutable permanent Delivery sequence")
    order_id: str
    customer_id: int
    tracking_no: str | None = None
    delivery_no: str
    delivery_date: date
    shipped_date: date
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DeliveryItemResponse(BaseModel):
    id: str
    uuid: str
    delivery_id: str
    order_item_id: str
    product_id: int
    delivery_line_no: str = Field(deprecated=True, description="Deprecated compatibility field; new rows mirror line_ref, not the legacy value format")
    line_no: int | None = Field(default=None, description="Immutable business line number within the Delivery")
    line_ref: str | None = Field(default=None, description="Authoritative globally unique human-readable line reference")
    delivered_qty: float = Field(description="Quantity delivered to the customer on the Product.order_uom axis")
    delivered_uom: str = Field(description="Customer order UOM copied from Product.order_uom")
    shipped_date: date
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
