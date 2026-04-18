from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import Customer, Order, OrderItem, Product, Supplier, SupplierAllocation
from app.schemas.report import ShippingReportRow, ShippingReportSortMode

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


def _latest_allocation_subquery(db: Session):
    latest_id_sq = (
        db.query(
            SupplierAllocation.order_item_id.label("order_item_id"),
            func.max(SupplierAllocation.id).label("latest_id"),
        )
        .group_by(SupplierAllocation.order_item_id)
        .subquery()
    )

    return (
        db.query(
            SupplierAllocation.order_item_id.label("order_item_id"),
            SupplierAllocation.final_supplier_id.label("final_supplier_id"),
            SupplierAllocation.final_qty.label("final_qty"),
        )
        .join(
            latest_id_sq,
            (SupplierAllocation.order_item_id == latest_id_sq.c.order_item_id)
            & (SupplierAllocation.id == latest_id_sq.c.latest_id),
        )
        .subquery()
    )


@router.get("/shipping", response_model=list[ShippingReportRow])
def shipping_report(
    shipped_date: date = Query(...),
    mode: ShippingReportSortMode = Query(default=ShippingReportSortMode.supplier_product),
    db: Session = Depends(get_db),
) -> list[ShippingReportRow]:
    alloc = _latest_allocation_subquery(db)

    query = (
        db.query(OrderItem, Order, Customer, Product, alloc.c.final_supplier_id, alloc.c.final_qty, Supplier)
        .join(Order, OrderItem.order_id == Order.id)
        .join(Customer, Order.customer_id == Customer.id)
        .join(Product, OrderItem.product_id == Product.id)
        .outerjoin(alloc, alloc.c.order_item_id == OrderItem.id)
        .outerjoin(Supplier, Supplier.id == alloc.c.final_supplier_id)
        .filter(OrderItem.shipped_date == shipped_date)
    )

    if mode == ShippingReportSortMode.supplier_product:
        query = query.order_by(Supplier.name.asc().nulls_last(), Product.name.asc(), Customer.name.asc(), OrderItem.id.asc())
    else:
        query = query.order_by(Customer.name.asc(), Supplier.name.asc().nulls_last(), Product.name.asc(), OrderItem.id.asc())

    rows = query.all()
    result: list[ShippingReportRow] = []
    for item, _order, customer, product, _supplier_id, final_qty, supplier in rows:
        qty = float(final_qty) if final_qty is not None else float(item.ordered_qty)
        result.append(
            ShippingReportRow(
                shipped_date=item.shipped_date,
                supplier_name=(supplier.name if supplier is not None else None),
                customer_name=customer.name,
                product_name=product.name,
                quantity=qty,
                unit=product.order_uom,
            )
        )

    return result
