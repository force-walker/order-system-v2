from datetime import datetime

from pydantic import BaseModel, Field


class PurchaseResultCreateRequest(BaseModel):
    allocation_id: int
    purchased_qty: float = Field(gt=0)
    purchased_uom: str
    result_status: str
    invoiceable_flag: bool = True
    note: str | None = None


class PurchaseResultUpdateRequest(BaseModel):
    purchased_qty: float | None = Field(default=None, gt=0)
    purchased_uom: str | None = None
    result_status: str | None = None
    invoiceable_flag: bool | None = None
    note: str | None = None


class PurchaseResultBulkUpsertRequest(BaseModel):
    items: list[PurchaseResultCreateRequest] = Field(min_length=1)


class PurchaseResultResponse(BaseModel):
    id: int
    allocation_id: int
    purchased_qty: float
    purchased_uom: str
    result_status: str
    invoiceable_flag: bool
    recorded_at: datetime
    note: str | None

    model_config = {"from_attributes": True}
