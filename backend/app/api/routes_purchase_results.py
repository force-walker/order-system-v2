from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.audit import AuditAction, write_audit_log
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


def _get_allocation_or_404(db: Session, allocation_id: int) -> SupplierAllocation:
    alloc = db.query(SupplierAllocation).filter(SupplierAllocation.id == allocation_id).first()
    if alloc is None:
        raise HTTPException(status_code=404, detail={"code": "ALLOCATION_NOT_FOUND", "message": "allocation not found"})
    return alloc


def _default_supplier_id(payload_supplier_id: int | None, alloc: SupplierAllocation) -> int | None:
    if payload_supplier_id is not None:
        return payload_supplier_id
    if alloc.final_supplier_id is not None:
        return alloc.final_supplier_id
    return alloc.suggested_supplier_id


def _validate_quantity_limit(
    db: Session,
    *,
    alloc: SupplierAllocation,
    incoming_qty: float,
    exclude_result_id: int | None = None,
) -> None:
    if alloc.final_qty is None:
        return

    query = db.query(PurchaseResult).filter(PurchaseResult.allocation_id == alloc.id)
    if exclude_result_id is not None:
        query = query.filter(PurchaseResult.id != exclude_result_id)

    accumulated = sum(Decimal(str(row.purchased_qty)) for row in query.all())
    total_after = accumulated + Decimal(str(incoming_qty))
    max_allowed = Decimal(str(alloc.final_qty))
    if total_after > max_allowed:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "PURCHASE_QTY_EXCEEDS_ALLOCATION",
                "message": "sum of purchased_qty exceeds allocation.final_qty",
            },
        )


@router.post(
    "",
    response_model=PurchaseResultResponse,
    status_code=201,
    responses={
        **PURCHASE_RESULT_COMMON_ERROR_RESPONSES,
        404: {"model": ApiErrorResponse, "description": "Not Found"},
    },
)
def create_purchase_result(payload: PurchaseResultCreateRequest, db: Session = Depends(get_db)) -> PurchaseResultResponse:
    alloc = _get_allocation_or_404(db, payload.allocation_id)
    _validate_quantity_limit(db, alloc=alloc, incoming_qty=payload.purchased_qty)

    row = PurchaseResult(
        **payload.model_dump(exclude={"supplier_id"}),
        supplier_id=_default_supplier_id(payload.supplier_id, alloc),
    )
    db.add(row)
    db.flush()
    write_audit_log(db, entity_type="purchase_result", entity_id=row.id, action=AuditAction.CREATE)
    db.commit()
    db.refresh(row)
    return PurchaseResultResponse.model_validate(row)


@router.get(
    "/{result_id}",
    response_model=PurchaseResultResponse,
    responses={404: {"model": ApiErrorResponse, "description": "Not Found"}},
)
def get_purchase_result(result_id: int, db: Session = Depends(get_db)) -> PurchaseResultResponse:
    row = db.query(PurchaseResult).filter(PurchaseResult.id == result_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "RESOURCE_NOT_FOUND", "message": "purchase result not found"})
    return PurchaseResultResponse.model_validate(row)


@router.get(
    "",
    response_model=list[PurchaseResultResponse],
    responses={**PURCHASE_RESULT_COMMON_ERROR_RESPONSES, 404: {"model": ApiErrorResponse, "description": "Not Found"}},
)
def list_purchase_results(
    allocation_id: int | None = Query(default=None, gt=0),
    db: Session = Depends(get_db),
) -> list[PurchaseResultResponse]:
    query = db.query(PurchaseResult)
    if allocation_id is not None:
        _get_allocation_or_404(db, allocation_id)
        query = query.filter(PurchaseResult.allocation_id == allocation_id)

    rows = query.order_by(PurchaseResult.recorded_at.asc(), PurchaseResult.id.asc()).all()
    return [PurchaseResultResponse.model_validate(row) for row in rows]


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

    alloc = _get_allocation_or_404(db, row.allocation_id)
    _validate_quantity_limit(db, alloc=alloc, incoming_qty=row.purchased_qty, exclude_result_id=row.id)

    if row.supplier_id is None:
        row.supplier_id = _default_supplier_id(None, alloc)

    db.flush()
    write_audit_log(db, entity_type="purchase_result", entity_id=row.id, action=AuditAction.UPDATE)
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
        alloc = _get_allocation_or_404(db, item.allocation_id)

        row = db.query(PurchaseResult).filter(PurchaseResult.allocation_id == item.allocation_id).first()
        if row is None:
            _validate_quantity_limit(db, alloc=alloc, incoming_qty=item.purchased_qty)
            row = PurchaseResult(
                **item.model_dump(exclude={"supplier_id"}),
                supplier_id=_default_supplier_id(item.supplier_id, alloc),
            )
            db.add(row)
            db.flush()
            write_audit_log(db, entity_type="purchase_result", entity_id=row.id, action=AuditAction.BULK_UPSERT_CREATE)
        else:
            for k, v in item.model_dump().items():
                setattr(row, k, v)
            if row.supplier_id is None:
                row.supplier_id = _default_supplier_id(None, alloc)
            _validate_quantity_limit(db, alloc=alloc, incoming_qty=row.purchased_qty, exclude_result_id=row.id)
            db.flush()
            write_audit_log(db, entity_type="purchase_result", entity_id=row.id, action=AuditAction.BULK_UPSERT_UPDATE)
        count += 1

    db.commit()
    return {"upserted_count": count}
