from datetime import date, datetime

from pydantic import BaseModel


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
