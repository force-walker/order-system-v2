from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.audit import AuditAction, write_audit_log
from app.db.session import get_db
from app.models.entities import Supplier
from app.schemas.common import ApiErrorResponse
from app.schemas.supplier import SupplierCreateRequest, SupplierResponse

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
