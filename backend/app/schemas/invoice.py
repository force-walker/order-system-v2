from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.entities import InvoiceStatus


class InvoiceCreateRequest(BaseModel):
    order_id: int = Field(gt=0)
    invoice_date: date
    due_date: date | None = None


class InvoiceGenerateRequest(BaseModel):
    order_id: int = Field(gt=0)
    invoice_date: date
    due_date: date | None = None


class InvoiceDraftFromPurchaseResultsRequest(BaseModel):
    order_id: int = Field(gt=0)
    invoice_date: date
    due_date: date | None = None
    purchase_result_ids: list[int] = Field(min_length=1)


class InvoiceResponse(BaseModel):
    id: int
    uuid: str
    tracking_no: str | None = None
    invoice_no: str
    invoice_draft_no: str | None = None
    official_invoice_no: str | None = None
    customer_id: int
    invoice_date: date
    delivery_date: date
    due_date: date | None
    subtotal: float
    tax_total: float
    grand_total: float
    status: InvoiceStatus
    is_locked: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class InvoiceItemResponse(BaseModel):
    id: int
    uuid: str
    invoice_id: int
    order_item_id: int
    invoice_line_no: str | None = None
    billable_qty: float
    billable_uom: str
    invoice_line_status: str
    sales_unit_price: float
    unit_cost_basis: float | None
    auto_price_error: str | None = None
    line_amount: float
    tax_amount: float
    gross_margin_pct: float | None = None
    gross_margin_unavailable: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class InvoiceDraftListRow(BaseModel):
    invoice_id: int
    invoice_item_id: int
    invoice_uuid: str
    invoice_item_uuid: str
    tracking_no: str | None = None
    invoice_no: str
    invoice_draft_no: str | None = None
    official_invoice_no: str | None = None
    invoice_line_no: str | None = None
    invoice_date: date
    delivery_date: date
    status: InvoiceStatus
    order_no: str
    customer_name: str
    product_name: str
    billable_qty: float
    billable_uom: str
    sales_unit_price: float
    unit_cost_basis: float | None = None
    auto_price_error: str | None = None
    line_amount: float
    gross_margin_pct: float | None = None
    gross_margin_unavailable: bool = False


class InvoiceItemUpdateRequest(BaseModel):
    billable_qty: float = Field(ge=0)
    billable_uom: str | None = Field(default=None, min_length=1, max_length=32)
    sales_unit_price: float = Field(ge=0)


class InvoiceDraftGenerateResult(BaseModel):
    invoice_id: int
    created_count: int
    target_purchase_result_ids: list[int]
    idempotent_hit: bool


class InvoiceDraftRecalculateResponse(BaseModel):
    invoice_id: int
    recalculated_count: int
    subtotal: float
    tax_total: float
    grand_total: float


class InvoiceReportLine(BaseModel):
    invoice_item_id: int
    invoice_item_uuid: str
    order_item_id: int
    invoice_line_no: str | None = None
    product_name: str
    billable_qty: float
    billable_uom: str
    sales_unit_price: float
    unit_cost_basis: float | None = None
    line_amount: float
    tax_amount: float
    gross_margin_pct: float | None = None
    gross_margin_unavailable: bool = False


class InvoiceReportResponse(BaseModel):
    invoice_id: int
    invoice_uuid: str
    tracking_no: str | None = None
    invoice_no: str
    invoice_draft_no: str | None = None
    official_invoice_no: str | None = None
    status: InvoiceStatus
    customer_id: int
    customer_name: str
    invoice_date: date
    delivery_date: date
    due_date: date | None
    subtotal: float
    tax_total: float
    grand_total: float
    items: list[InvoiceReportLine]


class InvoiceSummaryRow(BaseModel):
    invoice_id: int
    invoice_uuid: str
    tracking_no: str | None = None
    invoice_no: str
    invoice_draft_no: str | None = None
    official_invoice_no: str | None = None
    customer_name: str
    invoice_date: date
    delivery_date: date
    due_date: date | None
    status: InvoiceStatus
    subtotal: float
    tax_total: float
    grand_total: float
    item_count: int


class InvoiceNeighborsResponse(BaseModel):
    invoice_id: int
    prev_invoice_id: int | None
    next_invoice_id: int | None


class InvoiceFinalizeResponse(BaseModel):
    invoice_id: int
    invoice_no: str
    official_invoice_no: str | None = None
    status: InvoiceStatus
    is_locked: bool


class InvoiceBatchFinalizeRequest(BaseModel):
    invoice_ids: list[int] = Field(min_length=1)


class InvoiceBatchFinalizeResult(BaseModel):
    invoice_id: int
    ok: bool
    status: InvoiceStatus | None = None
    is_locked: bool | None = None
    reason_code: str | None = None
    message: str | None = None


class InvoiceBatchFinalizeResponse(BaseModel):
    success_count: int
    failure_count: int
    results: list[InvoiceBatchFinalizeResult]


class InvoiceResetRequest(BaseModel):
    reset_reason_code: str
    reason_note: str | None = None


class InvoiceUnlockRequest(BaseModel):
    unlock_reason_code: str
    reason_note: str | None = None


class InvoiceResetResponse(BaseModel):
    invoice_id: int
    status: InvoiceStatus


class InvoiceUnlockResponse(BaseModel):
    invoice_id: int
    status: InvoiceStatus
    is_locked: bool
