import enum
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PricingBasis(str, enum.Enum):
    uom_count = "uom_count"
    uom_kg = "uom_kg"


class OrderStatus(str, enum.Enum):
    new = "new"
    confirmed = "confirmed"
    allocated = "allocated"
    purchased = "purchased"
    shipped = "shipped"
    invoiced = "invoiced"
    cancelled = "cancelled"


class LineStatus(str, enum.Enum):
    open = "open"
    allocated = "allocated"
    purchased = "purchased"
    shipped = "shipped"
    invoiced = "invoiced"
    cancelled = "cancelled"


class StockoutPolicy(str, enum.Enum):
    backorder = "backorder"
    substitute = "substitute"
    cancel = "cancel"
    split = "split"


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    order_uom: Mapped[str] = mapped_column(String(32))
    purchase_uom: Mapped[str] = mapped_column(String(32))
    invoice_uom: Mapped[str] = mapped_column(String(32))
    is_catch_weight: Mapped[bool] = mapped_column(Boolean, default=False)
    weight_capture_required: Mapped[bool] = mapped_column(Boolean, default=False)
    pricing_basis_default: Mapped[PricingBasis] = mapped_column(Enum(PricingBasis, name="pricingbasis"), default=PricingBasis.uom_count)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_no: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    order_datetime: Mapped[datetime] = mapped_column(DateTime, index=True)
    delivery_date: Mapped[date] = mapped_column(Date, index=True)
    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus, name="orderstatus"), default=OrderStatus.new, index=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    ordered_qty: Mapped[float] = mapped_column(Numeric(12, 3))
    pricing_basis: Mapped[PricingBasis] = mapped_column(Enum(PricingBasis, name="pricingbasis"), default=PricingBasis.uom_count)
    unit_price_uom_count: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    unit_price_uom_kg: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    line_status: Mapped[LineStatus] = mapped_column(Enum(LineStatus, name="linestatus"), default=LineStatus.open, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SupplierAllocation(Base):
    __tablename__ = "supplier_allocations"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_item_id: Mapped[int] = mapped_column(ForeignKey("order_items.id"), index=True)
    final_supplier_id: Mapped[int | None] = mapped_column(index=True)
    final_qty: Mapped[float | None] = mapped_column(Numeric(12, 3), nullable=True)
    final_uom: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_manual_override: Mapped[bool] = mapped_column(Boolean, default=False)
    override_reason_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    stockout_policy: Mapped[StockoutPolicy | None] = mapped_column(Enum(StockoutPolicy, name="stockoutpolicy"), nullable=True)
    split_group_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PurchaseResult(Base):
    __tablename__ = "purchase_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    allocation_id: Mapped[int] = mapped_column(ForeignKey("supplier_allocations.id"), index=True)
    purchased_qty: Mapped[float] = mapped_column(Numeric(12, 3))
    purchased_uom: Mapped[str] = mapped_column(String(32))
    result_status: Mapped[str] = mapped_column(String(32), index=True)
    invoiceable_flag: Mapped[bool] = mapped_column(Boolean, default=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class InvoiceStatus(str, enum.Enum):
    draft = "draft"
    finalized = "finalized"
    sent = "sent"
    cancelled = "cancelled"


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_no: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    invoice_date: Mapped[date] = mapped_column(Date)
    delivery_date: Mapped[date] = mapped_column(Date)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    subtotal: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    tax_total: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    grand_total: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    status: Mapped[InvoiceStatus] = mapped_column(Enum(InvoiceStatus, name="invoicestatus"), default=InvoiceStatus.draft, index=True)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class BatchJobStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"


class BatchJob(Base):
    __tablename__ = "batch_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_type: Mapped[str] = mapped_column(String(64), index=True)
    business_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    trace_id: Mapped[str] = mapped_column(String(64), index=True)
    request_id: Mapped[str] = mapped_column(String(64), index=True)
    actor: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[BatchJobStatus] = mapped_column(Enum(BatchJobStatus, name="batchjobstatus"), default=BatchJobStatus.queued, index=True)
    retry_count: Mapped[int] = mapped_column(default=0)
    max_retries: Mapped[int] = mapped_column(default=1)
    requested_count: Mapped[int] = mapped_column(default=0)
    processed_count: Mapped[int] = mapped_column(default=0)
    succeeded_count: Mapped[int] = mapped_column(default=0)
    failed_count: Mapped[int] = mapped_column(default=0)
    skipped_count: Mapped[int] = mapped_column(default=0)
    errors_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(64), index=True)
    entity_id: Mapped[int] = mapped_column(index=True)
    action: Mapped[str] = mapped_column(String(64))
    reason_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    changed_by: Mapped[str] = mapped_column(String(64), index=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
