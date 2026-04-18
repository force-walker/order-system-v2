import enum
from datetime import date

from pydantic import BaseModel


class ShippingReportSortMode(str, enum.Enum):
    supplier_product = "supplier_product"
    customer = "customer"


class ShippingReportRow(BaseModel):
    shipped_date: date
    supplier_name: str | None
    customer_name: str
    product_name: str
    quantity: float
    unit: str
