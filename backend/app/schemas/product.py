from datetime import datetime

from pydantic import BaseModel

from app.models.entities import PricingBasis


class ProductResponse(BaseModel):
    id: int
    sku: str
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
