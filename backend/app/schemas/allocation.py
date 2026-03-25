from datetime import datetime

from pydantic import BaseModel, Field


class AllocationOverrideRequest(BaseModel):
    final_supplier_id: int
    final_qty: float = Field(gt=0)
    final_uom: str
    override_reason_code: str
    override_note: str | None = None


class SplitPart(BaseModel):
    final_supplier_id: int
    final_qty: float = Field(gt=0)
    final_uom: str


class AllocationSplitRequest(BaseModel):
    parts: list[SplitPart] = Field(min_length=2)
    override_reason_code: str
    override_note: str | None = None


class AllocationResponse(BaseModel):
    id: int
    order_item_id: int
    final_supplier_id: int | None
    final_qty: float | None
    final_uom: str | None
    is_manual_override: bool
    override_reason_code: str | None
    split_group_id: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
