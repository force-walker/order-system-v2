from datetime import date, datetime
from pydantic import BaseModel, Field, model_validator
from app.models.entities import PaymentTermsType, SupplierBillStatus

class SupplierBillCreateRequest(BaseModel):
    purchase_result_ids: list[int] = Field(min_length=1)
    supplier_invoice_no: str = Field(min_length=1, max_length=128)
    bill_date: date
    currency: str = Field(default="JPY", min_length=3, max_length=3)

    @model_validator(mode="after")
    def validate_values(self):
        self.supplier_invoice_no = self.supplier_invoice_no.strip()
        if not self.supplier_invoice_no:
            raise ValueError("supplier_invoice_no must not be blank")
        if self.currency.upper() != "JPY":
            raise ValueError("Supplier Bill currency must be JPY")
        self.currency = "JPY"
        return self

class SupplierBillItemUpdate(BaseModel):
    quantity: float = Field(gt=0)
    unit_cost: float | None = Field(default=None, ge=0)

class SupplierBillUpdateRequest(BaseModel):
    supplier_invoice_no: str | None = Field(default=None, min_length=1, max_length=128)
    bill_date: date | None = None
    tax: float | None = Field(default=None, ge=0)
    adjustment: float | None = None
    items: dict[str, SupplierBillItemUpdate] | None = None

    @model_validator(mode="after")
    def reject_explicit_nulls(self):
        required_if_present = ("supplier_invoice_no", "bill_date", "tax", "adjustment")
        for field in required_if_present:
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} must not be null")
        if self.supplier_invoice_no is not None:
            self.supplier_invoice_no = self.supplier_invoice_no.strip()
            if not self.supplier_invoice_no:
                raise ValueError("supplier_invoice_no must not be blank")
        return self

class SupplierPaymentCreateRequest(BaseModel):
    payment_date: date
    amount: float = Field(gt=0)
    reference: str | None = Field(default=None, max_length=128)
    note: str | None = None

class SupplierPaymentVoidRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=255)

class PayableCandidate(BaseModel):
    purchase_result_id: int; purchase_date: date; supplier_id: int; supplier_name: str
    order_no: str; line_no: int; product_id: int; sku: str; product_name: str
    quantity: float; uom: str; unit_cost: float | None; amount: float | None; currency: str = "JPY"

class SupplierBillItemResponse(BaseModel):
    id: str; line_no: int; purchase_result_id: int; product_id: int; sku: str; description: str
    quantity: float; uom: str; unit_cost: float | None; line_amount: float | None

class SupplierPaymentResponse(BaseModel):
    id: str; payment_date: date; amount: float; reference: str | None; note: str | None
    created_at: datetime; voided_at: datetime | None; void_reason: str | None

class SupplierBillResponse(BaseModel):
    id: str; document_seq: int; bill_no: str; supplier_id: int; supplier_name: str
    supplier_invoice_no: str; bill_date: date; due_date: date | None
    payment_terms_type: PaymentTermsType | None; payment_terms_days: int | None
    currency: str; status: SupplierBillStatus; subtotal: float; tax: float; adjustment: float; total_amount: float
    paid_amount: float; outstanding_amount: float; payment_status: str | None; overdue: bool; line_count: int
    items: list[SupplierBillItemResponse] = Field(default_factory=list)
    payments: list[SupplierPaymentResponse] = Field(default_factory=list)

class SupplierBillListResponse(BaseModel):
    items: list[SupplierBillResponse]; total: int; page: int; page_size: int

class SupplierBillNeighborsResponse(BaseModel):
    previous_id: str | None; next_id: str | None

class SupplierOutstandingResponse(BaseModel):
    supplier_id: int; outstanding_amount: float; currency: str = "JPY"
