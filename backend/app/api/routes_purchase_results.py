from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.audit import write_audit_log
from app.db.session import get_db
from app.models.entities import PurchaseResult, SupplierAllocation
from app.schemas.common import ApiErrorResponse
from app.schemas.purchase_result import (
    PurchaseResultBulkUpsertRequest,
    PurchaseResultCreateRequest,
    PurchaseResultResponse,
    PurchaseResultUpdateRequest,
)

router = APIRouter(prefix="/api/v1/purchase-results", tags=["purchase-results"])

PURCHASE_RESULT_COMMON_ERROR_RESPONSES = {
    422: {"model": ApiErrorResponse, "description": "Validation Error"},
}


@router.post(
    "",
    response_model=PurchaseResultResponse,
    status_code=201,
    responses={
        **PURCHASE_RESULT_COMMON_ERROR_RESPONSES,
        404: {"model": ApiErrorResponse, "description": "Not Found"},
        409: {"model": ApiErrorResponse, "description": "Conflict"},
    },
)
def create_purchase_result(payload: PurchaseResultCreateRequest, db: Session = Depends(get_db)) -> PurchaseResultResponse:
    alloc = db.query(SupplierAllocation).filter(SupplierAllocation.id == payload.allocation_id).first()
    if alloc is None:
        raise HTTPException(status_code=404, detail={"code": "ALLOCATION_NOT_FOUND", "message": "allocation not found"})

    exists = db.query(PurchaseResult).filter(PurchaseResult.allocation_id == payload.allocation_id).first()
    if exists is not None:
        raise HTTPException(
            status_code=409,
            detail={"code": "PURCHASE_RESULT_ALREADY_EXISTS", "message": "purchase result already exists for allocation"},
        )

    row = PurchaseResult(**payload.model_dump())
    db.add(row)
    db.flush()
    write_audit_log(db, entity_type="purchase_result", entity_id=row.id, action="create")
    db.commit()
    db.refresh(row)
    return PurchaseResultResponse.model_validate(row)


@router.patch(
    "/{result_id}",
    response_model=PurchaseResultResponse,
    responses={**PURCHASE_RESULT_COMMON_ERROR_RESPONSES, 404: {"model": ApiErrorResponse, "description": "Not Found"}},
)
def update_purchase_result(result_id: int, payload: PurchaseResultUpdateRequest, db: Session = Depends(get_db)) -> PurchaseResultResponse:
    row = db.query(PurchaseResult).filter(PurchaseResult.id == result_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "RESOURCE_NOT_FOUND", "message": "purchase result not found"})

    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(row, k, v)

    db.flush()
    write_audit_log(db, entity_type="purchase_result", entity_id=row.id, action="update")
    db.commit()
    db.refresh(row)
    return PurchaseResultResponse.model_validate(row)


@router.post(
    "/bulk-upsert",
    responses={**PURCHASE_RESULT_COMMON_ERROR_RESPONSES, 404: {"model": ApiErrorResponse, "description": "Not Found"}},
)
def bulk_upsert_purchase_results(payload: PurchaseResultBulkUpsertRequest, db: Session = Depends(get_db)) -> dict[str, int]:
    count = 0
    for item in payload.items:
        alloc = db.query(SupplierAllocation).filter(SupplierAllocation.id == item.allocation_id).first()
        if alloc is None:
            raise HTTPException(
                status_code=404,
                detail={"code": "ALLOCATION_NOT_FOUND", "message": f"allocation not found: {item.allocation_id}"},
            )

        row = db.query(PurchaseResult).filter(PurchaseResult.allocation_id == item.allocation_id).first()
        if row is None:
            row = PurchaseResult(**item.model_dump())
            db.add(row)
            db.flush()
            write_audit_log(db, entity_type="purchase_result", entity_id=row.id, action="bulk_upsert_create")
        else:
            for k, v in item.model_dump().items():
                setattr(row, k, v)
            db.flush()
            write_audit_log(db, entity_type="purchase_result", entity_id=row.id, action="bulk_upsert_update")
        count += 1

    db.commit()
    return {"upserted_count": count}
