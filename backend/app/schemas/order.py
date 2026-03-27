from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.entities import OrderStatus


class OrderCreateRequest(BaseModel):
    customer_id: int = Field(gt=0)
    delivery_date: date
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
