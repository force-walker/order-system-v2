from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.audit import AuditAction, write_audit_log
from app.db.session import get_db
from app.models.entities import Customer, LineStatus, Order, OrderItem, Product, Supplier, SupplierAllocation, SupplierProduct
from app.schemas.common import ApiErrorResponse
from app.schemas.order_item_allocation import (
    AllocationSuggestRequest,
    AllocationSuggestion,
    BulkAllocationQtySaveRequest,
    BulkAllocationSaveError,
    BulkAllocationSaveRequest,
    BulkAllocationSaveResponse,
    BulkAllocationSupplierSaveRequest,
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


def _ensure_allocation(db: Session, order_item_id: int) -> SupplierAllocation:
    alloc = _current_allocation(db, order_item_id)
    if alloc is not None:
        return alloc
    alloc = SupplierAllocation(order_item_id=order_item_id)
    db.add(alloc)
    db.flush()
    return alloc


def _apply_item_workflow_state(db: Session, item: OrderItem, alloc: SupplierAllocation) -> None:
    order = db.query(Order).filter(Order.id == item.order_id).first()
    if order is None:
        return

    has_supplier = alloc.final_supplier_id is not None
    has_qty = alloc.final_qty is not None and float(alloc.final_qty) > 0
    if has_supplier and has_qty:
        item.shipped_date = order.delivery_date
        item.line_status = LineStatus.allocated


@router.get("", response_model=list[OrderItemAllocationWorkItem])
def list_order_item_allocation_work_items(
    unallocated_only: bool = Query(default=False),
    delivery_date: date | None = Query(default=None),
    supplier_id: int | None = Query(default=None, gt=0),
    product_name: str | None = Query(default=None, min_length=1, max_length=255),
    customer_name: str | None = Query(default=None, min_length=1, max_length=255),
    limit: int | None = Query(default=None, ge=1, le=500),
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
        has_supplier = alloc is not None and alloc.final_supplier_id is not None
        has_qty = alloc is not None and alloc.final_qty is not None and float(alloc.final_qty) > 0
        has_alloc = has_supplier and has_qty
        if unallocated_only and has_alloc:
            continue
        if supplier_id is not None and (not has_supplier or alloc.final_supplier_id != supplier_id):
            continue

        result.append(
            OrderItemAllocationWorkItem(
                order_item_id=item.id,
                allocation_id=(alloc.id if alloc is not None else None),
                order_no=order.order_no,
                product_id=product.id,
                product_name=product.name,
                ordered_qty=float(item.ordered_qty),
                delivery_date=order.delivery_date,
                shipped_date=item.shipped_date,
                allocation_status=("allocated" if has_alloc else "unallocated"),
                allocated_supplier_id=(alloc.final_supplier_id if has_supplier else None),
                allocated_qty=(float(alloc.final_qty) if has_qty else None),
            )
        )
    if limit is None:
        return result[offset:]
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
    "/bulk-save-qty",
    response_model=BulkAllocationSaveResponse,
    responses={422: {"model": ApiErrorResponse, "description": "Validation Error"}, 409: {"model": ApiErrorResponse, "description": "Conflict"}},
)
def bulk_save_allocated_qty(payload: BulkAllocationQtySaveRequest, db: Session = Depends(get_db)) -> BulkAllocationSaveResponse:
    errors: list[BulkAllocationSaveError] = []
    succeeded = 0

    for row in payload.items:
        item = db.query(OrderItem).filter(OrderItem.id == row.order_item_id).first()
        if item is None:
            errors.append(BulkAllocationSaveError(order_item_id=row.order_item_id, code="ORDER_ITEM_NOT_FOUND", message="order_item not found"))
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

        alloc = _ensure_allocation(db, row.order_item_id)
        alloc.final_qty = row.allocated_qty
        alloc.final_uom = "count"
        alloc.is_manual_override = True
        alloc.override_reason_code = payload.override_reason_code

        _apply_item_workflow_state(db, item, alloc)

        db.flush()
        write_audit_log(db, entity_type="supplier_allocation", entity_id=alloc.id, action=AuditAction.OVERRIDE, reason_code=payload.override_reason_code)
        write_audit_log(db, entity_type="order_item", entity_id=item.id, action=AuditAction.UPDATE, reason_code="bulk_allocate_qty_apply")
        succeeded += 1

    db.commit()
    failed = len(payload.items) - succeeded
    return BulkAllocationSaveResponse(total=len(payload.items), succeeded=succeeded, failed=failed, errors=errors)


@router.post(
    "/bulk-save-suppliers",
    response_model=BulkAllocationSaveResponse,
    responses={422: {"model": ApiErrorResponse, "description": "Validation Error"}, 409: {"model": ApiErrorResponse, "description": "Conflict"}},
)
def bulk_save_suppliers(payload: BulkAllocationSupplierSaveRequest, db: Session = Depends(get_db)) -> BulkAllocationSaveResponse:
    errors: list[BulkAllocationSaveError] = []
    succeeded = 0

    for row in payload.items:
        item = db.query(OrderItem).filter(OrderItem.id == row.order_item_id).first()
        if item is None:
            errors.append(BulkAllocationSaveError(order_item_id=row.order_item_id, code="ORDER_ITEM_NOT_FOUND", message="order_item not found"))
            continue

        if row.supplier_id is not None:
            supplier = db.query(Supplier).filter(Supplier.id == row.supplier_id).first()
            if supplier is None:
                errors.append(BulkAllocationSaveError(order_item_id=row.order_item_id, code="SUPPLIER_NOT_FOUND", message="supplier not found"))
                continue

        alloc = _ensure_allocation(db, row.order_item_id)
        alloc.final_supplier_id = row.supplier_id
        alloc.is_manual_override = True
        alloc.override_reason_code = payload.override_reason_code

        _apply_item_workflow_state(db, item, alloc)

        db.flush()
        write_audit_log(db, entity_type="supplier_allocation", entity_id=alloc.id, action=AuditAction.OVERRIDE, reason_code=payload.override_reason_code)
        write_audit_log(db, entity_type="order_item", entity_id=item.id, action=AuditAction.UPDATE, reason_code="bulk_allocate_supplier_apply")
        succeeded += 1

    db.commit()
    failed = len(payload.items) - succeeded
    return BulkAllocationSaveResponse(total=len(payload.items), succeeded=succeeded, failed=failed, errors=errors)


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

        split_children = db.query(SupplierAllocation.id).filter(SupplierAllocation.order_item_id == row.order_item_id, SupplierAllocation.is_split_child.is_(True)).all()
        if split_children:
            errors.append(BulkAllocationSaveError(order_item_id=row.order_item_id, code="ALLOCATION_SPLIT_CONFLICT", message="split allocations exist; bulk-save not allowed"))
            continue

        alloc = _current_allocation(db, row.order_item_id)

        # unselect supplier = clear allocation
        if row.supplier_id is None:
            if row.allocated_qty is not None:
                errors.append(
                    BulkAllocationSaveError(
                        order_item_id=row.order_item_id,
                        code="UNASSIGN_WITH_QTY_NOT_ALLOWED",
                        message="allocated_qty must be null when supplier_id is null",
                    )
                )
                continue

            if alloc is None:
                succeeded += 1
                continue

            alloc.final_supplier_id = None
            alloc.final_qty = None
            alloc.final_uom = None
            alloc.is_manual_override = True
            alloc.override_reason_code = payload.override_reason_code
            db.flush()
            write_audit_log(db, entity_type="supplier_allocation", entity_id=alloc.id, action=AuditAction.OVERRIDE, reason_code=payload.override_reason_code)
            succeeded += 1
            continue

        supplier = db.query(Supplier).filter(Supplier.id == row.supplier_id).first()
        if supplier is None:
            errors.append(BulkAllocationSaveError(order_item_id=row.order_item_id, code="SUPPLIER_NOT_FOUND", message="supplier not found"))
            continue

        if row.allocated_qty is None:
            errors.append(BulkAllocationSaveError(order_item_id=row.order_item_id, code="ALLOCATED_QTY_REQUIRED", message="allocated_qty is required when supplier_id is set"))
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

        order = db.query(Order).filter(Order.id == item.order_id).first()
        if order is None:
            errors.append(BulkAllocationSaveError(order_item_id=row.order_item_id, code="ORDER_NOT_FOUND", message="order not found"))
            continue

        if alloc is None:
            alloc = SupplierAllocation(order_item_id=row.order_item_id)
            db.add(alloc)

        alloc.final_supplier_id = row.supplier_id
        alloc.final_qty = row.allocated_qty
        alloc.final_uom = "count"
        alloc.is_manual_override = True
        alloc.override_reason_code = payload.override_reason_code

        # reflect assignment to order-item level workflow
        item.shipped_date = order.delivery_date
        item.line_status = LineStatus.allocated

        db.flush()
        write_audit_log(db, entity_type="supplier_allocation", entity_id=alloc.id, action=AuditAction.OVERRIDE, reason_code=payload.override_reason_code)
        write_audit_log(db, entity_type="order_item", entity_id=item.id, action=AuditAction.UPDATE, reason_code="bulk_allocate_apply")
        succeeded += 1

    db.commit()
    failed = len(payload.items) - succeeded
    return BulkAllocationSaveResponse(total=len(payload.items), succeeded=succeeded, failed=failed, errors=errors)
