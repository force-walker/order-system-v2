from datetime import datetime

from pydantic import BaseModel, Field


class AllocationOverrideRequest(BaseModel):
    final_supplier_id: int = Field(gt=0)
    final_qty: float = Field(gt=0)
    final_uom: str = Field(min_length=1, max_length=32)
    override_reason_code: str = Field(min_length=1, max_length=64)
    override_note: str | None = Field(default=None, max_length=1000)


class SplitPart(BaseModel):
    final_supplier_id: int = Field(gt=0)
    final_qty: float = Field(gt=0)
    final_uom: str = Field(min_length=1, max_length=32)


class AllocationSplitRequest(BaseModel):
    parts: list[SplitPart] = Field(min_length=2)
    override_reason_code: str = Field(min_length=1, max_length=64)
    override_note: str | None = Field(default=None, max_length=1000)


class AllocationResponse(BaseModel):
    id: int
    order_item_id: int
    suggested_supplier_id: int | None
    suggested_qty: float | None
    final_supplier_id: int | None
    final_qty: float | None
    final_uom: str | None
    is_manual_override: bool
    override_reason_code: str | None
    target_price: float | None
    split_group_id: str | None
    parent_allocation_id: int | None
    is_split_child: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
