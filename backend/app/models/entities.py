import enum
from datetime import UTC, date, datetime

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, Enum, ForeignKey, Index, Numeric, String, Text
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
    customer_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))


class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(primary_key=True)
    supplier_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))


class SupplierProduct(Base):
    __tablename__ = "supplier_products"
    __table_args__ = (
        Index("ix_supplier_products_supplier_id_product_id", "supplier_id", "product_id", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    priority: Mapped[int] = mapped_column(default=100)
    is_preferred: Mapped[bool] = mapped_column(Boolean, default=False)
    default_unit_cost: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    lead_time_days: Mapped[int | None] = mapped_column(nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    legacy_code: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    import_key: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True, index=True)
    legacy_unit_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    category_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    product_type_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    name: Mapped[str] = mapped_column(String(255))
    name_kana: Mapped[str | None] = mapped_column(String(255), nullable=True)
    name_kana_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    pack_size: Mapped[int | None] = mapped_column(nullable=True)
    tax_category_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    inventory_category_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    owner_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    origin_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    jan_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    sales_price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    sales_price_1: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    sales_price_2: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    sales_price_3: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    sales_price_4: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    sales_price_5: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    sales_price_6: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    purchase_price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    inventory_price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    list_price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    tax_rate_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    handling_category_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    name_en: Mapped[str | None] = mapped_column(String(255), nullable=True)
    name_zh_hk: Mapped[str | None] = mapped_column(String(255), nullable=True)
    customs_reference_price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    customs_origin_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    chayafuda_flag: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    application_category_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    order_uom: Mapped[str] = mapped_column(String(32))
    purchase_uom: Mapped[str] = mapped_column(String(32))
    invoice_uom: Mapped[str] = mapped_column(String(32))
    is_catch_weight: Mapped[bool] = mapped_column(Boolean, default=False)
    weight_capture_required: Mapped[bool] = mapped_column(Boolean, default=False)
    pricing_basis_default: Mapped[PricingBasis] = mapped_column(Enum(PricingBasis, name="pricingbasis"), default=PricingBasis.uom_count)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_no: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    order_datetime: Mapped[datetime] = mapped_column(DateTime, index=True)
    delivery_date: Mapped[date] = mapped_column(Date, index=True)
    shipped_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus, name="orderstatus"), default=OrderStatus.new, index=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(64), default="system_api", index=True)
    updated_by: Mapped[str] = mapped_column(String(64), default="system_api", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))


class OrderItem(Base):
    __tablename__ = "order_items"
    __table_args__ = (
        CheckConstraint("ordered_qty > 0", name="ck_order_items_ordered_qty_positive"),
        CheckConstraint(
            "(pricing_basis != 'uom_count' OR unit_price_uom_count IS NOT NULL)"
            " AND (pricing_basis != 'uom_kg' OR unit_price_uom_kg IS NOT NULL)",
            name="ck_order_items_price_required_by_pricing_basis",
        ),
        CheckConstraint("target_price IS NULL OR target_price >= 0", name="ck_order_items_target_price_non_negative"),
        CheckConstraint("price_ceiling IS NULL OR price_ceiling >= 0", name="ck_order_items_price_ceiling_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    ordered_qty: Mapped[float] = mapped_column(Numeric(12, 3))
    order_uom_type: Mapped[PricingBasis] = mapped_column(Enum(PricingBasis, name="pricingbasis"), default=PricingBasis.uom_count)
    estimated_weight_kg: Mapped[float | None] = mapped_column(Numeric(12, 3), nullable=True)
    actual_weight_kg: Mapped[float | None] = mapped_column(Numeric(12, 3), nullable=True)
    shipped_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    target_price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    price_ceiling: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    stockout_policy: Mapped[StockoutPolicy | None] = mapped_column(Enum(StockoutPolicy, name="stockoutpolicy"), nullable=True)
    pricing_basis: Mapped[PricingBasis] = mapped_column(Enum(PricingBasis, name="pricingbasis"), default=PricingBasis.uom_count)
    unit_price_uom_count: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    unit_price_uom_kg: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    line_status: Mapped[LineStatus] = mapped_column(Enum(LineStatus, name="linestatus"), default=LineStatus.open, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))


class SupplierAllocation(Base):
    __tablename__ = "supplier_allocations"
    __table_args__ = (
        CheckConstraint("final_qty IS NULL OR final_qty >= 0", name="ck_supplier_allocations_final_qty_non_negative"),
        CheckConstraint("suggested_qty IS NULL OR suggested_qty > 0", name="ck_supplier_allocations_suggested_qty_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    order_item_id: Mapped[int] = mapped_column(ForeignKey("order_items.id"), index=True)
    suggested_supplier_id: Mapped[int | None] = mapped_column(index=True, nullable=True)
    suggested_qty: Mapped[float | None] = mapped_column(Numeric(12, 3), nullable=True)
    final_supplier_id: Mapped[int | None] = mapped_column(index=True)
    final_qty: Mapped[float | None] = mapped_column(Numeric(12, 3), nullable=True)
    final_uom: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_manual_override: Mapped[bool] = mapped_column(Boolean, default=False)
    override_reason_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    target_price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    stockout_policy: Mapped[StockoutPolicy | None] = mapped_column(Enum(StockoutPolicy, name="stockoutpolicy"), nullable=True)
    split_group_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    parent_allocation_id: Mapped[int | None] = mapped_column(ForeignKey("supplier_allocations.id"), nullable=True, index=True)
    is_split_child: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))


class PurchaseResultStatus(str, enum.Enum):
    not_filled = "not_filled"
    filled = "filled"
    partially_filled = "partially_filled"
    substituted = "substituted"


class PurchaseResult(Base):
    __tablename__ = "purchase_results"
    __table_args__ = (
        CheckConstraint("purchased_qty > 0", name="ck_purchase_results_purchased_qty_positive"),
        CheckConstraint("actual_weight_kg IS NULL OR actual_weight_kg > 0", name="ck_purchase_results_actual_weight_positive"),
        CheckConstraint("unit_cost IS NULL OR unit_cost >= 0", name="ck_purchase_results_unit_cost_non_negative"),
        CheckConstraint("final_unit_cost IS NULL OR final_unit_cost >= 0", name="ck_purchase_results_final_unit_cost_non_negative"),
        CheckConstraint("shortage_qty IS NULL OR shortage_qty >= 0", name="ck_purchase_results_shortage_qty_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    allocation_id: Mapped[int] = mapped_column(ForeignKey("supplier_allocations.id"), index=True)
    supplier_id: Mapped[int | None] = mapped_column(index=True, nullable=True)
    purchased_qty: Mapped[float] = mapped_column(Numeric(12, 3))
    purchased_uom: Mapped[str] = mapped_column(String(32))
    actual_weight_kg: Mapped[float | None] = mapped_column(Numeric(12, 3), nullable=True)
    unit_cost: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    final_unit_cost: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    shortage_qty: Mapped[float | None] = mapped_column(Numeric(12, 3), nullable=True)
    shortage_policy: Mapped[StockoutPolicy | None] = mapped_column(Enum(StockoutPolicy, name="stockoutpolicy"), nullable=True)
    result_status: Mapped[PurchaseResultStatus] = mapped_column(
        Enum(PurchaseResultStatus, name="purchaseresultstatus"),
        default=PurchaseResultStatus.not_filled,
        index=True,
    )
    invoiceable_flag: Mapped[bool] = mapped_column(Boolean, default=True)
    recorded_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_deferred: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    defer_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    defer_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    deferred_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    deferred_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class InvoiceStatus(str, enum.Enum):
    draft = "draft"
    finalized = "finalized"
    sent = "sent"
    cancelled = "cancelled"


class Invoice(Base):
    __tablename__ = "invoices"
    __table_args__ = (
        CheckConstraint("due_date IS NULL OR due_date >= invoice_date", name="ck_invoices_due_date_gte_invoice_date"),
        CheckConstraint("subtotal >= 0", name="ck_invoices_subtotal_non_negative"),
        CheckConstraint("tax_total >= 0", name="ck_invoices_tax_total_non_negative"),
        CheckConstraint("grand_total >= 0", name="ck_invoices_grand_total_non_negative"),
    )

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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))


class InvoiceLineStatus(str, enum.Enum):
    uninvoiced = "uninvoiced"
    partially_invoiced = "partially_invoiced"
    invoiced = "invoiced"
    cancelled = "cancelled"


class InvoiceItem(Base):
    __tablename__ = "invoice_items"
    __table_args__ = (
        CheckConstraint("sales_unit_price >= 0", name="ck_invoice_items_sales_unit_price_non_negative"),
        Index("ix_invoice_items_invoice_id", "invoice_id"),
        Index("ix_invoice_items_order_item_id", "order_item_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"))
    order_item_id: Mapped[int] = mapped_column(ForeignKey("order_items.id"))
    billable_qty: Mapped[float] = mapped_column(Numeric(12, 3))
    billable_uom: Mapped[str] = mapped_column(String(32))
    invoice_line_status: Mapped[InvoiceLineStatus] = mapped_column(
        Enum(InvoiceLineStatus, name="invoicelinestatus"),
        default=InvoiceLineStatus.uninvoiced,
        index=True,
    )
    sales_unit_price: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    unit_cost_basis: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    line_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    tax_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))


class BatchJobStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"


class BatchJob(Base):
    __tablename__ = "batch_jobs"
    __table_args__ = (
        CheckConstraint("retry_count >= 0", name="ck_batch_jobs_retry_count_non_negative"),
        CheckConstraint("max_retries >= 1", name="ck_batch_jobs_max_retries_min_one"),
        CheckConstraint("retry_count <= max_retries", name="ck_batch_jobs_retry_count_lte_max_retries"),
        CheckConstraint("requested_count >= 0", name="ck_batch_jobs_requested_count_non_negative"),
        CheckConstraint("processed_count >= 0", name="ck_batch_jobs_processed_count_non_negative"),
        CheckConstraint("succeeded_count >= 0", name="ck_batch_jobs_succeeded_count_non_negative"),
        CheckConstraint("failed_count >= 0", name="ck_batch_jobs_failed_count_non_negative"),
        CheckConstraint("skipped_count >= 0", name="ck_batch_jobs_skipped_count_non_negative"),
        Index("ix_batch_jobs_type_business_date_status", "job_type", "business_date", "status"),
    )

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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_entity_type_entity_id_changed_at", "entity_type", "entity_id", "changed_at"),
        Index("ix_audit_logs_changed_by_changed_at", "changed_by", "changed_at"),
        Index("ix_audit_logs_trace_id", "trace_id"),
        Index("ix_audit_logs_request_id", "request_id"),
        Index("ix_audit_logs_job_id", "job_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(64), index=True)
    entity_id: Mapped[int] = mapped_column(index=True)
    action: Mapped[str] = mapped_column(String(64))
    before_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    after_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    changed_by: Mapped[str] = mapped_column(String(64), index=True)
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    job_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), index=True)
