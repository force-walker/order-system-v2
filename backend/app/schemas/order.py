from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.entities import OrderStatus


class OrderCreateRequest(BaseModel):
    order_no: str = Field(min_length=1, max_length=64)
    customer_id: int
    delivery_date: date
    note: str | None = None


class OrderResponse(BaseModel):
    id: int
    order_no: str
    customer_id: int
    order_datetime: datetime
    delivery_date: date
    status: OrderStatus
    note: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
