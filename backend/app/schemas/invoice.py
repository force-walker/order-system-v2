from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.entities import InvoiceStatus


class InvoiceCreateRequest(BaseModel):
    invoice_no: str = Field(min_length=1, max_length=64)
    order_id: int
    invoice_date: date
    due_date: date | None = None


class InvoiceResponse(BaseModel):
    id: int
    invoice_no: str
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


class InvoiceFinalizeResponse(BaseModel):
    invoice_id: int
    status: InvoiceStatus
    is_locked: bool


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
