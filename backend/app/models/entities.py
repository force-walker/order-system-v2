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
