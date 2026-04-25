from datetime import date

from pydantic import BaseModel, Field


class OrderItemAllocationWorkItem(BaseModel):
    order_item_id: int
    allocation_id: int | None = None
    order_no: str
    product_id: int
    product_name: str
    ordered_qty: float
    delivery_date: date
    shipped_date: date | None = None
    allocation_status: str
    allocated_supplier_id: int | None = None
    allocated_qty: float | None = None


class AllocationSuggestion(BaseModel):
    order_item_id: int
    suggested_supplier_id: int | None
    suggested_qty: float | None
    reason: str


class AllocationSuggestRequest(BaseModel):
    order_item_ids: list[int] = Field(min_length=1, max_length=500)


class BulkAllocationSaveItem(BaseModel):
    order_item_id: int = Field(gt=0)
    supplier_id: int | None = Field(default=None, gt=0)
    allocated_qty: float | None = Field(default=None, gt=0)


class BulkAllocationQtySaveItem(BaseModel):
    order_item_id: int = Field(gt=0)
    allocated_qty: float = Field(gt=0)


class BulkAllocationSupplierSaveItem(BaseModel):
    order_item_id: int = Field(gt=0)
    supplier_id: int | None = Field(default=None, gt=0)


class BulkAllocationSaveRequest(BaseModel):
    items: list[BulkAllocationSaveItem] = Field(min_length=1, max_length=500)
    override_reason_code: str | None = Field(default="bulk_manual", max_length=64)


class BulkAllocationQtySaveRequest(BaseModel):
    items: list[BulkAllocationQtySaveItem] = Field(min_length=1, max_length=500)
    override_reason_code: str | None = Field(default="bulk_qty_manual", max_length=64)


class BulkAllocationSupplierSaveRequest(BaseModel):
    items: list[BulkAllocationSupplierSaveItem] = Field(min_length=1, max_length=500)
    override_reason_code: str | None = Field(default="bulk_supplier_manual", max_length=64)


class BulkAllocationSaveError(BaseModel):
    order_item_id: int
    code: str
    message: str


class BulkAllocationSaveResponse(BaseModel):
    total: int
    succeeded: int
    failed: int
    errors: list[BulkAllocationSaveError]
