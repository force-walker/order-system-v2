from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.audit import AuditAction, write_audit_log
from app.db.session import get_db
from app.models.entities import PurchaseResult, Supplier, SupplierAllocation
from app.schemas.common import ApiErrorResponse
from app.schemas.supplier import SupplierCreateRequest, SupplierResponse, SupplierUpdateRequest

router = APIRouter(prefix="/api/v1/suppliers", tags=["suppliers"])

SUPPLIER_COMMON_ERROR_RESPONSES = {
    422: {"model": ApiErrorResponse, "description": "Validation Error"},
}


@router.get("", response_model=list[SupplierResponse])
def list_suppliers(db: Session = Depends(get_db)) -> list[SupplierResponse]:
    rows = db.query(Supplier).order_by(Supplier.id.asc()).all()
    return [SupplierResponse.model_validate(row) for row in rows]


@router.get(
    "/{supplier_id}",
    response_model=SupplierResponse,
    responses={**SUPPLIER_COMMON_ERROR_RESPONSES, 404: {"model": ApiErrorResponse, "description": "Not Found"}},
)
def get_supplier(supplier_id: int, db: Session = Depends(get_db)) -> SupplierResponse:
    row = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "SUPPLIER_NOT_FOUND", "message": "supplier not found"})
    return SupplierResponse.model_validate(row)


@router.post(
    "",
    response_model=SupplierResponse,
    status_code=201,
    responses={
        **SUPPLIER_COMMON_ERROR_RESPONSES,
        409: {"model": ApiErrorResponse, "description": "Conflict"},
    },
)
def create_supplier(payload: SupplierCreateRequest, db: Session = Depends(get_db)) -> SupplierResponse:
    exists = db.query(Supplier).filter(Supplier.supplier_code == payload.supplier_code).first()
    if exists is not None:
        raise HTTPException(status_code=409, detail={"code": "SUPPLIER_CODE_ALREADY_EXISTS", "message": "supplier code already exists"})

    row = Supplier(supplier_code=payload.supplier_code, name=payload.name, active=payload.active)
    db.add(row)
    db.flush()
    write_audit_log(db, entity_type="supplier", entity_id=row.id, action=AuditAction.CREATE)
    db.commit()
    db.refresh(row)
    return SupplierResponse.model_validate(row)


@router.patch(
    "/{supplier_id}",
    response_model=SupplierResponse,
    responses={**SUPPLIER_COMMON_ERROR_RESPONSES, 404: {"model": ApiErrorResponse, "description": "Not Found"}},
)
def update_supplier(supplier_id: int, payload: SupplierUpdateRequest, db: Session = Depends(get_db)) -> SupplierResponse:
    row = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "SUPPLIER_NOT_FOUND", "message": "supplier not found"})

    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(row, k, v)

    db.flush()
    write_audit_log(db, entity_type="supplier", entity_id=row.id, action=AuditAction.UPDATE)
    db.commit()
    db.refresh(row)
    return SupplierResponse.model_validate(row)


@router.delete(
    "/{supplier_id}",
    status_code=204,
    responses={
        **SUPPLIER_COMMON_ERROR_RESPONSES,
        404: {"model": ApiErrorResponse, "description": "Not Found"},
        409: {"model": ApiErrorResponse, "description": "Conflict"},
    },
)
def delete_supplier(supplier_id: int, db: Session = Depends(get_db)) -> Response:
    row = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "SUPPLIER_NOT_FOUND", "message": "supplier not found"})

    has_allocation_ref = (
        db.query(SupplierAllocation.id)
        .filter(or_(SupplierAllocation.suggested_supplier_id == supplier_id, SupplierAllocation.final_supplier_id == supplier_id))
        .first()
        is not None
    )
    has_purchase_ref = db.query(PurchaseResult.id).filter(PurchaseResult.supplier_id == supplier_id).first() is not None

    if has_allocation_ref or has_purchase_ref:
        raise HTTPException(
            status_code=409,
            detail={"code": "SUPPLIER_IN_USE", "message": "supplier is referenced by allocation or purchase result"},
        )

    db.delete(row)
    db.flush()
    write_audit_log(db, entity_type="supplier", entity_id=supplier_id, action=AuditAction.CANCEL)
    db.commit()
    return Response(status_code=204)
