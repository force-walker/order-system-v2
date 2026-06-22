import enum
from datetime import date

from pydantic import BaseModel, Field


class ShippingReportSortMode(str, enum.Enum):
    supplier_product = "supplier_product"
    customer = "customer"


class ShippingReportRow(BaseModel):
    delivery_id: str
    delivery_item_id: str
    delivery_no: str
    order_item_id: str
    shipped_date: date
    supplier_name: str | None
    customer_name: str
    product_name: str
    quantity: float
    unit: str


class PurchaseConfirmationPdfRequest(BaseModel):
    selected_ids: list[str | int] = Field(min_length=1, max_length=1000)
    sort: str = "product_desc"
