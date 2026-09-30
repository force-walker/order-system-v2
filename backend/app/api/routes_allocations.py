from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import Order, OrderItem, OrderStatus, PurchaseResult, SupplierAllocation
from app.core.allocation_completion import evaluate_order_allocation_completion, synchronize_confirmed_order_allocation_status
from app.core.auth import AuthContext, get_auth_context
from app.core.audit import AuditAction, write_audit_log
from app.schemas.allocation import AllocationOverrideRequest, AllocationResponse, AllocationSplitRequest
from app.schemas.common import ApiErrorResponse

router = APIRouter(prefix="/api/v1/allocations", tags=["allocations"])

ALLOCATION_COMMON_ERROR_RESPONSES = {
    422: {"model": ApiErrorResponse, "description": "Validation Error"},
    409: {"model": ApiErrorResponse, "description": "Conflict"},
}


def _lock_allocation_order(db: Session, allocation: SupplierAllocation) -> Order:
    item = db.query(OrderItem).filter(OrderItem.id == allocation.order_item_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail={"code": "ORDER_ITEM_NOT_FOUND", "message": "order item not found"})
    order = db.query(Order).filter(Order.id == item.order_id).with_for_update().first()
    if order is None:
        raise HTTPException(status_code=404, detail={"code": "ORDER_NOT_FOUND", "message": "order not found"})
    # Serialize Allocation edits with Purchase Result creation, which locks the
    # same allocation row before establishing the downstream dependency.
    db.query(SupplierAllocation.id).filter(SupplierAllocation.id == allocation.id).with_for_update().one()
    db.refresh(allocation)
    return order


def _norm_uom(value: str | None) -> str:
    return (value or "").strip().casefold()


def _item_has_purchase_result(db: Session, order_item_id: str) -> bool:
    return db.query(PurchaseResult.id).join(SupplierAllocation, SupplierAllocation.id == PurchaseResult.allocation_id).filter(SupplierAllocation.order_item_id == order_item_id).first() is not None


def _ensure_changed_allocation_is_editable(db: Session, order_item_id: str) -> None:
    if _item_has_purchase_result(db, order_item_id):
        raise HTTPException(status_code=409, detail={"code": "ALLOCATION_LOCKED_BY_PURCHASE_RESULT", "message": "purchase result exists; allocation cannot be changed"})


def _ensure_order_allocation_change_editable(order: Order) -> None:
    if order.status not in {OrderStatus.confirmed, OrderStatus.allocated}:
        raise HTTPException(status_code=409, detail={"code": "ORDER_NOT_ALLOCATION_EDITABLE", "message": "allocation changes require a confirmed or allocated order"})


def _ensure_allocated_order_remains_complete(db: Session, order: Order) -> None:
    if order.status != OrderStatus.allocated:
        return
    result = evaluate_order_allocation_completion(db, order.id)
    if not result.complete:
        raise HTTPException(status_code=422, detail={"code": "ALLOCATION_COMPLETION_REQUIRED", "message": "allocated order must remain allocation-complete", "details": [reason.__dict__ for reason in result.reasons]})


@router.patch(
    "/{allocation_id}/override",
    response_model=AllocationResponse,
    responses={**ALLOCATION_COMMON_ERROR_RESPONSES, 404: {"model": ApiErrorResponse, "description": "Not Found"}},
)
def override_allocation(
    allocation_id: int,
    payload: AllocationOverrideRequest,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> AllocationResponse:
    row = db.query(SupplierAllocation).filter(SupplierAllocation.id == allocation_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "ALLOCATION_NOT_FOUND", "message": "allocation not found"})
    order = _lock_allocation_order(db, row)

    unchanged = (
        row.final_supplier_id == payload.final_supplier_id
        and (None if row.final_qty is None else float(row.final_qty)) == payload.final_qty
        and _norm_uom(row.final_uom) == _norm_uom(payload.final_uom)
        and row.split_group_id is None
    )
    if unchanged:
        return AllocationResponse.model_validate(row)
    _ensure_order_allocation_change_editable(order)
    _ensure_changed_allocation_is_editable(db, row.order_item_id)

    before = {"final_supplier_id": row.final_supplier_id, "final_qty": float(row.final_qty) if row.final_qty is not None else None, "final_uom": row.final_uom, "split_group_id": row.split_group_id}
    row.final_supplier_id = payload.final_supplier_id
    row.final_qty = payload.final_qty
    row.final_uom = payload.final_uom
    row.is_manual_override = True
    row.override_reason_code = payload.override_reason_code
    row.is_split_child = False

    db.flush()
    write_audit_log(
        db,
        entity_type="supplier_allocation",
        entity_id=row.id,
        action=AuditAction.OVERRIDE,
        actor=auth.user_id,
        reason_code=payload.override_reason_code,
        before=before,
        after={"final_supplier_id": row.final_supplier_id, "final_qty": float(row.final_qty), "final_uom": row.final_uom, "split_group_id": row.split_group_id},
    )
    synchronize_confirmed_order_allocation_status(db, order)
    _ensure_allocated_order_remains_complete(db, order)
    db.commit()
    db.refresh(row)
    return AllocationResponse.model_validate(row)


@router.post(
    "/{allocation_id}/split-line",
    response_model=list[AllocationResponse],
    responses={**ALLOCATION_COMMON_ERROR_RESPONSES, 404: {"model": ApiErrorResponse, "description": "Not Found"}},
)
def split_allocation(
    allocation_id: int,
    payload: AllocationSplitRequest,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> list[AllocationResponse]:
    if any(part.final_supplier_id is None for part in payload.parts):
        raise HTTPException(
            status_code=422,
            detail={
                "code": "ALLOCATION_SUPPLIER_REQUIRED",
                "message": "final supplier is required for every split allocation row",
            },
        )
    row = db.query(SupplierAllocation).filter(SupplierAllocation.id == allocation_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "ALLOCATION_NOT_FOUND", "message": "allocation not found"})
    order = _lock_allocation_order(db, row)

    current_children = (
        db.query(SupplierAllocation)
        .filter(SupplierAllocation.parent_allocation_id == row.id, SupplierAllocation.is_split_child.is_(True), SupplierAllocation.split_group_id == row.split_group_id)
        .order_by(SupplierAllocation.id.asc())
        .all()
        if row.split_group_id is not None
        else []
    )
    current_signature = sorted((child.final_supplier_id, float(child.final_qty), _norm_uom(child.final_uom)) for child in current_children)
    requested_signature = sorted((part.final_supplier_id, part.final_qty, _norm_uom(part.final_uom)) for part in payload.parts)
    if len(current_children) == len(payload.parts) and current_signature == requested_signature:
        return [AllocationResponse.model_validate(child) for child in current_children]
    _ensure_order_allocation_change_editable(order)
    _ensure_changed_allocation_is_editable(db, row.order_item_id)

    group_id = f"split-{uuid4().hex[:12]}"
    row.split_group_id = group_id
    row.is_split_child = False

    created: list[SupplierAllocation] = []
    for p in payload.parts:
        child = SupplierAllocation(
            order_item_id=row.order_item_id,
            suggested_supplier_id=row.suggested_supplier_id,
            suggested_qty=row.suggested_qty,
            final_supplier_id=p.final_supplier_id,
            final_qty=p.final_qty,
            final_uom=p.final_uom,
            is_manual_override=True,
            override_reason_code=payload.override_reason_code,
            target_price=row.target_price,
            split_group_id=group_id,
            parent_allocation_id=row.id,
            is_split_child=True,
        )
        db.add(child)
        created.append(child)

    db.flush()
    for c in created:
        write_audit_log(
            db,
            entity_type="supplier_allocation",
            entity_id=c.id,
            action=AuditAction.SPLIT_LINE,
            actor=auth.user_id,
            reason_code=payload.override_reason_code,
        )
    synchronize_confirmed_order_allocation_status(db, order)
    _ensure_allocated_order_remains_complete(db, order)
    db.commit()
    for c in created:
        db.refresh(c)

    return [AllocationResponse.model_validate(c) for c in created]
