from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import SupplierAllocation
from app.core.audit import AuditAction, write_audit_log
from app.schemas.allocation import AllocationOverrideRequest, AllocationResponse, AllocationSplitRequest
from app.schemas.common import ApiErrorResponse

router = APIRouter(prefix="/api/v1/allocations", tags=["allocations"])

ALLOCATION_COMMON_ERROR_RESPONSES = {
    422: {"model": ApiErrorResponse, "description": "Validation Error"},
}


@router.patch(
    "/{allocation_id}/override",
    response_model=AllocationResponse,
    responses={**ALLOCATION_COMMON_ERROR_RESPONSES, 404: {"model": ApiErrorResponse, "description": "Not Found"}},
)
def override_allocation(allocation_id: int, payload: AllocationOverrideRequest, db: Session = Depends(get_db)) -> AllocationResponse:
    row = db.query(SupplierAllocation).filter(SupplierAllocation.id == allocation_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "ALLOCATION_NOT_FOUND", "message": "allocation not found"})

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
        reason_code=payload.override_reason_code,
    )
    db.commit()
    db.refresh(row)
    return AllocationResponse.model_validate(row)


@router.post(
    "/{allocation_id}/split-line",
    response_model=list[AllocationResponse],
    responses={**ALLOCATION_COMMON_ERROR_RESPONSES, 404: {"model": ApiErrorResponse, "description": "Not Found"}},
)
def split_allocation(allocation_id: int, payload: AllocationSplitRequest, db: Session = Depends(get_db)) -> list[AllocationResponse]:
    row = db.query(SupplierAllocation).filter(SupplierAllocation.id == allocation_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "ALLOCATION_NOT_FOUND", "message": "allocation not found"})

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
            reason_code=payload.override_reason_code,
        )
    db.commit()
    for c in created:
        db.refresh(c)

    return [AllocationResponse.model_validate(c) for c in created]
