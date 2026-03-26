from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import SupplierAllocation
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
    created: list[SupplierAllocation] = []
    for p in payload.parts:
        child = SupplierAllocation(
            order_item_id=row.order_item_id,
            final_supplier_id=p.final_supplier_id,
            final_qty=p.final_qty,
            final_uom=p.final_uom,
            is_manual_override=True,
            override_reason_code=payload.override_reason_code,
            split_group_id=group_id,
        )
        db.add(child)
        created.append(child)

    db.commit()
    for c in created:
        db.refresh(c)

    return [AllocationResponse.model_validate(c) for c in created]
