from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.entities import (
    BatchJob,
    BatchJobStatus,
    Customer,
    Invoice,
    InvoiceStatus,
    LineStatus,
    Order,
    OrderItem,
    OrderStatus,
    PricingBasis,
    Product,
    PurchaseResult,
    SupplierAllocation,
)


def get_or_create_product(db: Session, sku: str, name: str) -> Product:
    row = db.query(Product).filter(Product.sku == sku).first()
    if row:
        return row
    row = Product(
        sku=sku,
        name=name,
        order_uom="count",
        purchase_uom="count",
        invoice_uom="count",
        is_catch_weight=False,
        weight_capture_required=False,
        pricing_basis_default=PricingBasis.uom_count,
        active=True,
    )
    db.add(row)
    db.flush()
    return row


def get_or_create_customer(db: Session, code: str, name: str) -> Customer:
    row = db.query(Customer).filter(Customer.customer_code == code).first()
    if row:
        return row
    row = Customer(customer_code=code, name=name, active=True)
    db.add(row)
    db.flush()
    return row


def main() -> None:
    db = SessionLocal()
    try:
        product_a = get_or_create_product(db, "SKU-MOCK-APPLE", "Mock Apple")
        _product_b = get_or_create_product(db, "SKU-MOCK-BANANA", "Mock Banana")
        customer = get_or_create_customer(db, "CUST-MOCK-001", "Mockup Customer")

        order = db.query(Order).filter(Order.order_no == "ORD-MOCK-001").first()
        if not order:
            order = Order(
                order_no="ORD-MOCK-001",
                customer_id=customer.id,
                order_datetime=datetime.now(UTC),
                delivery_date=date.today(),
                status=OrderStatus.confirmed,
                note="seed for frontend mockup",
            )
            db.add(order)
            db.flush()

        item = db.query(OrderItem).filter(OrderItem.order_id == order.id, OrderItem.product_id == product_a.id).first()
        if not item:
            item = OrderItem(
                order_id=order.id,
                product_id=product_a.id,
                ordered_qty=5,
                pricing_basis=PricingBasis.uom_count,
                unit_price_uom_count=120,
                unit_price_uom_kg=None,
                line_status=LineStatus.open,
            )
            db.add(item)
            db.flush()

        alloc = db.query(SupplierAllocation).filter(SupplierAllocation.order_item_id == item.id).first()
        if not alloc:
            alloc = SupplierAllocation(
                order_item_id=item.id,
                final_supplier_id=101,
                final_qty=5,
                final_uom="count",
                is_manual_override=False,
            )
            db.add(alloc)
            db.flush()

        pr = db.query(PurchaseResult).filter(PurchaseResult.allocation_id == alloc.id).first()
        if not pr:
            pr = PurchaseResult(
                allocation_id=alloc.id,
                purchased_qty=5,
                purchased_uom="count",
                result_status="filled",
                invoiceable_flag=True,
                note="seed purchase result",
            )
            db.add(pr)
            db.flush()

        inv = db.query(Invoice).filter(Invoice.invoice_no == "INV-MOCK-001").first()
        if not inv:
            inv = Invoice(
                invoice_no="INV-MOCK-001",
                customer_id=customer.id,
                invoice_date=date.today(),
                delivery_date=order.delivery_date,
                due_date=date.today(),
                subtotal=600,
                tax_total=60,
                grand_total=660,
                status=InvoiceStatus.draft,
                is_locked=False,
            )
            db.add(inv)
            db.flush()

        job = db.query(BatchJob).filter(BatchJob.idempotency_key == "idem-mock-seed-001").first()
        if not job:
            job = BatchJob(
                job_type="allocation_run",
                business_date=date.today(),
                idempotency_key="idem-mock-seed-001",
                trace_id="trace-mock-seed-001",
                request_id="request-mock-seed-001",
                actor="seed_script",
                status=BatchJobStatus.succeeded,
                retry_count=0,
                max_retries=1,
                requested_count=1,
                processed_count=1,
                succeeded_count=1,
                failed_count=0,
                skipped_count=0,
                errors_json="[]",
                started_at=datetime.now(UTC),
                finished_at=datetime.now(UTC),
            )
            db.add(job)

        db.commit()

        print("Seed completed:")
        print("- products: SKU-MOCK-APPLE, SKU-MOCK-BANANA")
        print("- customer: CUST-MOCK-001")
        print("- order: ORD-MOCK-001")
        print("- invoice: INV-MOCK-001")
        print("- batch idempotency_key: idem-mock-seed-001")

    finally:
        db.close()


if __name__ == "__main__":
    main()
