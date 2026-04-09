from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.audit import AuditAction, write_audit_log
from app.core.codegen import generate_next_code
from app.db.session import get_db
from app.models.entities import Product, PurchaseResult, Supplier, SupplierAllocation, SupplierProduct
from app.schemas.common import ApiErrorResponse
from app.schemas.supplier import SupplierCreateRequest, SupplierResponse, SupplierUpdateRequest
from app.schemas.supplier_product import SupplierProductCreateRequest, SupplierProductResponse, SupplierProductUpdateRequest

router = APIRouter(prefix="/api/v1/suppliers", tags=["suppliers"])

SUPPLIER_COMMON_ERROR_RESPONSES = {
    422: {"model": ApiErrorResponse, "description": "Validation Error"},
}


@router.get("", response_model=list[SupplierResponse])
def list_suppliers(
    q: str | None = Query(default=None, min_length=1, max_length=255),
    include_inactive: bool = Query(default=False),
    active: bool | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[SupplierResponse]:
    query = db.query(Supplier)
    if q is not None:
        pattern = f"%{q}%"
        query = query.filter(or_(Supplier.supplier_code.ilike(pattern), Supplier.name.ilike(pattern)))

    if active is not None:
        query = query.filter(Supplier.active == active)
    elif not include_inactive:
        query = query.filter(Supplier.active.is_(True))

    rows = query.order_by(Supplier.id.asc()).offset(offset).limit(limit).all()
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
    supplier_code = generate_next_code(db, Supplier, "supplier_code", prefix="SUP-")

    exists = db.query(Supplier).filter(Supplier.supplier_code == supplier_code).first()
    if exists is not None:
        raise HTTPException(status_code=409, detail={"code": "SUPPLIER_CODE_ALREADY_EXISTS", "message": "supplier code already exists"})

    row = Supplier(supplier_code=supplier_code, name=payload.name, active=payload.active)
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


@router.post(
    "/{supplier_id}/archive",
    response_model=SupplierResponse,
    responses={404: {"model": ApiErrorResponse, "description": "Not Found"}},
)
def archive_supplier(supplier_id: int, db: Session = Depends(get_db)) -> SupplierResponse:
    row = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "SUPPLIER_NOT_FOUND", "message": "supplier not found"})

    row.active = False
    db.flush()
    write_audit_log(db, entity_type="supplier", entity_id=supplier_id, action=AuditAction.UPDATE, after={"active": row.active})
    db.commit()
    db.refresh(row)
    return SupplierResponse.model_validate(row)


@router.post(
    "/{supplier_id}/unarchive",
    response_model=SupplierResponse,
    responses={404: {"model": ApiErrorResponse, "description": "Not Found"}},
)
def unarchive_supplier(supplier_id: int, db: Session = Depends(get_db)) -> SupplierResponse:
    row = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "SUPPLIER_NOT_FOUND", "message": "supplier not found"})

    row.active = True
    db.flush()
    write_audit_log(db, entity_type="supplier", entity_id=supplier_id, action=AuditAction.UPDATE, after={"active": row.active})
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
    has_mapping_ref = db.query(SupplierProduct.id).filter(SupplierProduct.supplier_id == supplier_id).first() is not None

    if has_allocation_ref or has_purchase_ref or has_mapping_ref:
        raise HTTPException(status_code=409, detail={"code": "SUPPLIER_IN_USE", "message": "supplier is referenced and cannot be deleted"})

    db.delete(row)
    db.flush()
    write_audit_log(db, entity_type="supplier", entity_id=supplier_id, action=AuditAction.CANCEL)
    db.commit()
    return Response(status_code=204)


@router.get(
    "/{supplier_id}/products",
    response_model=list[SupplierProductResponse],
    responses={404: {"model": ApiErrorResponse, "description": "Not Found"}},
)
def list_supplier_products(supplier_id: int, db: Session = Depends(get_db)) -> list[SupplierProductResponse]:
    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if supplier is None:
        raise HTTPException(status_code=404, detail={"code": "SUPPLIER_NOT_FOUND", "message": "supplier not found"})

    rows = db.query(SupplierProduct).filter(SupplierProduct.supplier_id == supplier_id).order_by(SupplierProduct.priority.asc(), SupplierProduct.id.asc()).all()
    return [SupplierProductResponse.model_validate(row) for row in rows]


@router.post(
    "/{supplier_id}/products",
    response_model=SupplierProductResponse,
    status_code=201,
    responses={
        **SUPPLIER_COMMON_ERROR_RESPONSES,
        404: {"model": ApiErrorResponse, "description": "Not Found"},
        409: {"model": ApiErrorResponse, "description": "Conflict"},
    },
)
def create_supplier_product(
    supplier_id: int,
    payload: SupplierProductCreateRequest,
    db: Session = Depends(get_db),
) -> SupplierProductResponse:
    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if supplier is None:
        raise HTTPException(status_code=404, detail={"code": "SUPPLIER_NOT_FOUND", "message": "supplier not found"})

    product = db.query(Product).filter(Product.id == payload.product_id).first()
    if product is None:
        raise HTTPException(status_code=404, detail={"code": "PRODUCT_NOT_FOUND", "message": "product not found"})

    exists = db.query(SupplierProduct).filter(SupplierProduct.supplier_id == supplier_id, SupplierProduct.product_id == payload.product_id).first()
    if exists is not None:
        raise HTTPException(status_code=409, detail={"code": "SUPPLIER_PRODUCT_ALREADY_EXISTS", "message": "supplier-product mapping already exists"})

    row = SupplierProduct(supplier_id=supplier_id, **payload.model_dump())
    db.add(row)
    db.flush()
    write_audit_log(db, entity_type="supplier_product", entity_id=row.id, action=AuditAction.CREATE)
    db.commit()
    db.refresh(row)
    return SupplierProductResponse.model_validate(row)


@router.patch(
    "/{supplier_id}/products/{product_id}",
    response_model=SupplierProductResponse,
    responses={
        **SUPPLIER_COMMON_ERROR_RESPONSES,
        404: {"model": ApiErrorResponse, "description": "Not Found"},
    },
)
def update_supplier_product(
    supplier_id: int,
    product_id: int,
    payload: SupplierProductUpdateRequest,
    db: Session = Depends(get_db),
) -> SupplierProductResponse:
    row = db.query(SupplierProduct).filter(SupplierProduct.supplier_id == supplier_id, SupplierProduct.product_id == product_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "SUPPLIER_PRODUCT_NOT_FOUND", "message": "supplier-product mapping not found"})

    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(row, k, v)

    db.flush()
    write_audit_log(db, entity_type="supplier_product", entity_id=row.id, action=AuditAction.UPDATE)
    db.commit()
    db.refresh(row)
    return SupplierProductResponse.model_validate(row)


@router.delete(
    "/{supplier_id}/products/{product_id}",
    status_code=204,
    responses={404: {"model": ApiErrorResponse, "description": "Not Found"}},
)
def delete_supplier_product(supplier_id: int, product_id: int, db: Session = Depends(get_db)) -> Response:
    row = db.query(SupplierProduct).filter(SupplierProduct.supplier_id == supplier_id, SupplierProduct.product_id == product_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "SUPPLIER_PRODUCT_NOT_FOUND", "message": "supplier-product mapping not found"})

    db.delete(row)
    db.flush()
    write_audit_log(db, entity_type="supplier_product", entity_id=row.id, action=AuditAction.CANCEL)
    db.commit()
    return Response(status_code=204)
