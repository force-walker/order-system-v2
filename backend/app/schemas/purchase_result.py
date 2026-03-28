from datetime import datetime

from pydantic import BaseModel, Field

from app.models.entities import PurchaseResultStatus


class PurchaseResultCreateRequest(BaseModel):
    allocation_id: int = Field(gt=0)
    supplier_id: int | None = Field(default=None, gt=0)
    purchased_qty: float = Field(gt=0)
    purchased_uom: str = Field(min_length=1, max_length=32)
    actual_weight_kg: float | None = Field(default=None, gt=0)
    unit_cost: float | None = Field(default=None, ge=0)
    final_unit_cost: float | None = Field(default=None, ge=0)
    shortage_qty: float | None = Field(default=None, ge=0)
    shortage_policy: str | None = Field(default=None, min_length=1, max_length=32)
    result_status: PurchaseResultStatus
    invoiceable_flag: bool = True
    recorded_by: str | None = Field(default=None, min_length=1, max_length=64)
    note: str | None = Field(default=None, max_length=1000)


class PurchaseResultUpdateRequest(BaseModel):
    supplier_id: int | None = Field(default=None, gt=0)
    purchased_qty: float | None = Field(default=None, gt=0)
    purchased_uom: str | None = Field(default=None, min_length=1, max_length=32)
    actual_weight_kg: float | None = Field(default=None, gt=0)
    unit_cost: float | None = Field(default=None, ge=0)
    final_unit_cost: float | None = Field(default=None, ge=0)
    shortage_qty: float | None = Field(default=None, ge=0)
    shortage_policy: str | None = Field(default=None, min_length=1, max_length=32)
    result_status: PurchaseResultStatus | None = None
    invoiceable_flag: bool | None = None
    recorded_by: str | None = Field(default=None, min_length=1, max_length=64)
    note: str | None = Field(default=None, max_length=1000)


class PurchaseResultBulkUpsertRequest(BaseModel):
    items: list[PurchaseResultCreateRequest] = Field(min_length=1)


class PurchaseResultResponse(BaseModel):
    id: int
    allocation_id: int
    supplier_id: int | None
    purchased_qty: float
    purchased_uom: str
    actual_weight_kg: float | None
    unit_cost: float | None
    final_unit_cost: float | None
    shortage_qty: float | None
    shortage_policy: str | None
    result_status: PurchaseResultStatus
    invoiceable_flag: bool
    recorded_by: str | None
    recorded_at: datetime
    note: str | None

    model_config = {"from_attributes": True}
