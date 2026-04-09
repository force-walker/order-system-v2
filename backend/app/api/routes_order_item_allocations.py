from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.audit import AuditAction, write_audit_log
from app.db.session import get_db
from app.models.entities import Customer, Order, OrderItem, Product, Supplier, SupplierAllocation, SupplierProduct
from app.schemas.common import ApiErrorResponse
from app.schemas.order_item_allocation import (
    AllocationSuggestRequest,
    AllocationSuggestion,
    BulkAllocationSaveError,
    BulkAllocationSaveRequest,
    BulkAllocationSaveResponse,
    OrderItemAllocationWorkItem,
)

router = APIRouter(prefix="/api/v1/order-item-allocations", tags=["order-item-allocations"])


def _current_allocation(db: Session, order_item_id: int) -> SupplierAllocation | None:
    return (
        db.query(SupplierAllocation)
        .filter(SupplierAllocation.order_item_id == order_item_id, SupplierAllocation.is_split_child.is_(False))
        .order_by(SupplierAllocation.id.desc())
        .first()
    )


@router.get("", response_model=list[OrderItemAllocationWorkItem])
def list_order_item_allocation_work_items(
    unallocated_only: bool = Query(default=False),
    delivery_date: date | None = Query(default=None),
    supplier_id: int | None = Query(default=None, gt=0),
    product_name: str | None = Query(default=None, min_length=1, max_length=255),
    customer_name: str | None = Query(default=None, min_length=1, max_length=255),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[OrderItemAllocationWorkItem]:
    query = (
        db.query(OrderItem, Order, Product, Customer)
        .join(Order, OrderItem.order_id == Order.id)
        .join(Product, OrderItem.product_id == Product.id)
        .join(Customer, Order.customer_id == Customer.id)
    )

    if delivery_date is not None:
        query = query.filter(Order.delivery_date == delivery_date)
    if product_name is not None:
        query = query.filter(Product.name.ilike(f"%{product_name}%"))
    if customer_name is not None:
        query = query.filter(Customer.name.ilike(f"%{customer_name}%"))

    rows = query.order_by(Order.delivery_date.asc(), Order.id.asc(), OrderItem.id.asc()).all()

    result: list[OrderItemAllocationWorkItem] = []
    for item, order, product, _customer in rows:
        alloc = _current_allocation(db, item.id)
        has_alloc = alloc is not None and alloc.final_supplier_id is not None and alloc.final_qty is not None and float(alloc.final_qty) > 0
        if unallocated_only and has_alloc:
            continue
        if supplier_id is not None and (not has_alloc or alloc.final_supplier_id != supplier_id):
            continue

        result.append(
            OrderItemAllocationWorkItem(
                order_item_id=item.id,
                order_no=order.order_no,
                product_id=product.id,
                product_name=product.name,
                ordered_qty=float(item.ordered_qty),
                delivery_date=order.delivery_date,
                allocation_status=("allocated" if has_alloc else "unallocated"),
                allocated_supplier_id=(alloc.final_supplier_id if has_alloc else None),
                allocated_qty=(float(alloc.final_qty) if has_alloc else None),
            )
        )
    return result[offset : offset + limit]


@router.post(
    "/suggestions",
    response_model=list[AllocationSuggestion],
    responses={422: {"model": ApiErrorResponse, "description": "Validation Error"}, 404: {"model": ApiErrorResponse, "description": "Not Found"}},
)
def suggest_allocations(payload: AllocationSuggestRequest, db: Session = Depends(get_db)) -> list[AllocationSuggestion]:
    suggestions: list[AllocationSuggestion] = []
    for order_item_id in payload.order_item_ids:
        item = db.query(OrderItem).filter(OrderItem.id == order_item_id).first()
        if item is None:
            raise HTTPException(status_code=404, detail={"code": "ORDER_ITEM_NOT_FOUND", "message": f"order_item not found: {order_item_id}"})

        mapping = (
            db.query(SupplierProduct)
            .filter(SupplierProduct.product_id == item.product_id)
            .order_by(SupplierProduct.is_preferred.desc(), SupplierProduct.priority.asc(), SupplierProduct.id.asc())
            .first()
        )

        suggestions.append(
            AllocationSuggestion(
                order_item_id=item.id,
                suggested_supplier_id=(mapping.supplier_id if mapping is not None else None),
                suggested_qty=float(item.ordered_qty),
                reason=(
                    f"derived from supplier_product mapping(id={mapping.id}, preferred={mapping.is_preferred}, priority={mapping.priority})"
                    if mapping is not None
                    else "no supplier_product mapping found"
                ),
            )
        )
        write_audit_log(db, entity_type="order_item", entity_id=item.id, action=AuditAction.UPDATE, reason_code="auto_suggest")

    db.commit()
    return suggestions


@router.post(
    "/bulk-save",
    response_model=BulkAllocationSaveResponse,
    responses={422: {"model": ApiErrorResponse, "description": "Validation Error"}, 409: {"model": ApiErrorResponse, "description": "Conflict"}},
)
def bulk_save_allocations(payload: BulkAllocationSaveRequest, db: Session = Depends(get_db)) -> BulkAllocationSaveResponse:
    errors: list[BulkAllocationSaveError] = []
    succeeded = 0

    for row in payload.items:
        item = db.query(OrderItem).filter(OrderItem.id == row.order_item_id).first()
        if item is None:
            errors.append(BulkAllocationSaveError(order_item_id=row.order_item_id, code="ORDER_ITEM_NOT_FOUND", message="order_item not found"))
            continue

        supplier = db.query(Supplier).filter(Supplier.id == row.supplier_id).first()
        if supplier is None:
            errors.append(BulkAllocationSaveError(order_item_id=row.order_item_id, code="SUPPLIER_NOT_FOUND", message="supplier not found"))
            continue

        if row.allocated_qty > float(item.ordered_qty):
            errors.append(
                BulkAllocationSaveError(
                    order_item_id=row.order_item_id,
                    code="ALLOCATED_QTY_EXCEEDS_ORDERED_QTY",
                    message="allocated_qty must be <= ordered_qty",
                )
            )
            continue

        split_children = db.query(SupplierAllocation.id).filter(SupplierAllocation.order_item_id == row.order_item_id, SupplierAllocation.is_split_child.is_(True)).all()
        if split_children:
            errors.append(BulkAllocationSaveError(order_item_id=row.order_item_id, code="ALLOCATION_SPLIT_CONFLICT", message="split allocations exist; bulk-save not allowed"))
            continue

        alloc = _current_allocation(db, row.order_item_id)
        if alloc is None:
            alloc = SupplierAllocation(order_item_id=row.order_item_id)
            db.add(alloc)

        alloc.final_supplier_id = row.supplier_id
        alloc.final_qty = row.allocated_qty
        alloc.final_uom = "count"
        alloc.is_manual_override = True
        alloc.override_reason_code = payload.override_reason_code

        db.flush()
        write_audit_log(db, entity_type="supplier_allocation", entity_id=alloc.id, action=AuditAction.OVERRIDE, reason_code=payload.override_reason_code)
        succeeded += 1

    db.commit()
    failed = len(payload.items) - succeeded
    return BulkAllocationSaveResponse(total=len(payload.items), succeeded=succeeded, failed=failed, errors=errors)
