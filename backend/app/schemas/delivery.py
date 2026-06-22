from datetime import date, datetime

from pydantic import BaseModel, field_validator


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
    delivery_line_no: str
    delivered_qty: float
    delivered_uom: str
    shipped_date: date
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
