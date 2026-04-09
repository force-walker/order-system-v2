from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.core.audit import AuditAction, write_audit_log
from app.db.session import get_db
from app.models.entities import Product, Supplier, SupplierProduct
from app.schemas.common import ApiErrorResponse
from app.schemas.supplier_product import SupplierProductMappingCreateRequest, SupplierProductResponse, SupplierProductUpdateRequest

router = APIRouter(prefix="/api/v1/supplier-product-mappings", tags=["supplier-product-mappings"])


@router.get("", response_model=list[SupplierProductResponse])
def list_supplier_product_mappings(
    supplier_id: int | None = Query(default=None, gt=0),
    product_id: int | None = Query(default=None, gt=0),
    db: Session = Depends(get_db),
) -> list[SupplierProductResponse]:
    query = db.query(SupplierProduct)
    if supplier_id is not None:
        query = query.filter(SupplierProduct.supplier_id == supplier_id)
    if product_id is not None:
        query = query.filter(SupplierProduct.product_id == product_id)
    rows = query.order_by(SupplierProduct.priority.asc(), SupplierProduct.id.asc()).all()
    return [SupplierProductResponse.model_validate(row) for row in rows]


@router.post(
    "",
    response_model=SupplierProductResponse,
    status_code=201,
    responses={
        404: {"model": ApiErrorResponse, "description": "Not Found"},
        409: {"model": ApiErrorResponse, "description": "Conflict"},
        422: {"model": ApiErrorResponse, "description": "Validation Error"},
    },
)
def create_supplier_product_mapping(
    payload: SupplierProductMappingCreateRequest,
    db: Session = Depends(get_db),
) -> SupplierProductResponse:
    supplier = db.query(Supplier).filter(Supplier.id == payload.supplier_id).first()
    if supplier is None:
        raise HTTPException(status_code=404, detail={"code": "SUPPLIER_NOT_FOUND", "message": "supplier not found"})

    product = db.query(Product).filter(Product.id == payload.product_id).first()
    if product is None:
        raise HTTPException(status_code=404, detail={"code": "PRODUCT_NOT_FOUND", "message": "product not found"})

    exists = (
        db.query(SupplierProduct)
        .filter(SupplierProduct.supplier_id == payload.supplier_id, SupplierProduct.product_id == payload.product_id)
        .first()
    )
    if exists is not None:
        raise HTTPException(
            status_code=409,
            detail={"code": "SUPPLIER_PRODUCT_ALREADY_EXISTS", "message": "supplier-product mapping already exists"},
        )

    payload_data = payload.model_dump()
    row = SupplierProduct(**payload_data)
    db.add(row)
    db.flush()
    write_audit_log(db, entity_type="supplier_product", entity_id=row.id, action=AuditAction.CREATE)
    db.commit()
    db.refresh(row)
    return SupplierProductResponse.model_validate(row)


@router.patch(
    "/{mapping_id}",
    response_model=SupplierProductResponse,
    responses={
        404: {"model": ApiErrorResponse, "description": "Not Found"},
        422: {"model": ApiErrorResponse, "description": "Validation Error"},
    },
)
def update_supplier_product_mapping(
    mapping_id: int,
    payload: SupplierProductUpdateRequest,
    db: Session = Depends(get_db),
) -> SupplierProductResponse:
    row = db.query(SupplierProduct).filter(SupplierProduct.id == mapping_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "SUPPLIER_PRODUCT_NOT_FOUND", "message": "supplier-product mapping not found"})

    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(row, k, v)

    db.flush()
    write_audit_log(db, entity_type="supplier_product", entity_id=row.id, action=AuditAction.UPDATE)
    db.commit()
    db.refresh(row)
    return SupplierProductResponse.model_validate(row)


@router.delete(
    "/{mapping_id}",
    status_code=204,
    responses={404: {"model": ApiErrorResponse, "description": "Not Found"}},
)
def delete_supplier_product_mapping(mapping_id: int, db: Session = Depends(get_db)) -> Response:
    row = db.query(SupplierProduct).filter(SupplierProduct.id == mapping_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "SUPPLIER_PRODUCT_NOT_FOUND", "message": "supplier-product mapping not found"})

    db.delete(row)
    db.flush()
    write_audit_log(db, entity_type="supplier_product", entity_id=row.id, action=AuditAction.CANCEL)
    db.commit()
    return Response(status_code=204)
