from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.core.audit import AuditAction, write_audit_log
from app.core.codegen import generate_next_code
from app.db.session import get_db
from app.models.entities import OrderItem, Product, SupplierProduct
from app.schemas.common import ApiErrorResponse
from app.schemas.product import (
    BulkOperationError,
    BulkOperationSummary,
    ProductBulkCreateRequest,
    ProductBulkDeleteRequest,
    ProductBulkOperationResponse,
    ProductBulkUpdateRequest,
    ProductBulkUpsertRequest,
    ProductCreateRequest,
    ProductImportRequest,
    ProductImportResult,
    ProductResponse,
    ProductUpdateRequest,
)

router = APIRouter(prefix="/api/v1/products", tags=["products"])

PRODUCT_COMMON_ERROR_RESPONSES = {
    422: {"model": ApiErrorResponse, "description": "Validation Error"},
}


@router.get("", response_model=list[ProductResponse])
def list_products(
    include_inactive: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> list[ProductResponse]:
    query = db.query(Product)
    if not include_inactive:
        query = query.filter(Product.active.is_(True))
    rows = query.order_by(Product.id.asc()).all()
    return [ProductResponse.model_validate(r) for r in rows]


@router.get(
    "/{product_id}",
    response_model=ProductResponse,
    responses={**PRODUCT_COMMON_ERROR_RESPONSES, 404: {"model": ApiErrorResponse, "description": "Not Found"}},
)
def get_product(product_id: int, db: Session = Depends(get_db)) -> ProductResponse:
    row = db.query(Product).filter(Product.id == product_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "PRODUCT_NOT_FOUND", "message": "product not found"})
    return ProductResponse.model_validate(row)


@router.patch(
    "/{product_id}",
    response_model=ProductResponse,
    responses={**PRODUCT_COMMON_ERROR_RESPONSES, 404: {"model": ApiErrorResponse, "description": "Not Found"}},
)
def update_product(product_id: int, payload: ProductUpdateRequest, db: Session = Depends(get_db)) -> ProductResponse:
    row = db.query(Product).filter(Product.id == product_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "PRODUCT_NOT_FOUND", "message": "product not found"})

    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(row, k, v)

    db.flush()
    write_audit_log(db, entity_type="product", entity_id=row.id, action=AuditAction.UPDATE)
    db.commit()
    db.refresh(row)
    return ProductResponse.model_validate(row)


@router.post(
    "",
    response_model=ProductResponse,
    status_code=201,
    responses={
        **PRODUCT_COMMON_ERROR_RESPONSES,
        409: {"model": ApiErrorResponse, "description": "Conflict"},
    },
)
def create_product(payload: ProductCreateRequest, db: Session = Depends(get_db)) -> ProductResponse:
    sku = generate_next_code(db, Product, "sku", prefix="SKU-")

    exists = db.query(Product).filter(Product.sku == sku).first()
    if exists is not None:
        raise HTTPException(status_code=409, detail={"code": "SKU_ALREADY_EXISTS", "message": "sku already exists"})

    row = Product(
        sku=sku,
        name=payload.name,
        legacy_code=payload.legacy_code,
        legacy_unit_code=payload.legacy_unit_code,
        order_uom=payload.order_uom,
        purchase_uom=payload.purchase_uom,
        invoice_uom=payload.invoice_uom,
        is_catch_weight=payload.is_catch_weight,
        weight_capture_required=payload.weight_capture_required,
        pricing_basis_default=payload.pricing_basis_default,
        active=True,
    )
    db.add(row)
    db.flush()
    write_audit_log(db, entity_type="product", entity_id=row.id, action=AuditAction.CREATE)
    db.commit()
    db.refresh(row)
    return ProductResponse.model_validate(row)


@router.post(
    "/{product_id}/archive",
    response_model=ProductResponse,
    responses={404: {"model": ApiErrorResponse, "description": "Not Found"}},
)
def archive_product(product_id: int, db: Session = Depends(get_db)) -> ProductResponse:
    row = db.query(Product).filter(Product.id == product_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "PRODUCT_NOT_FOUND", "message": "product not found"})

    row.active = False
    db.flush()
    write_audit_log(db, entity_type="product", entity_id=row.id, action=AuditAction.UPDATE, after={"active": row.active})
    db.commit()
    db.refresh(row)
    return ProductResponse.model_validate(row)


@router.post(
    "/{product_id}/unarchive",
    response_model=ProductResponse,
    responses={404: {"model": ApiErrorResponse, "description": "Not Found"}},
)
def unarchive_product(product_id: int, db: Session = Depends(get_db)) -> ProductResponse:
    row = db.query(Product).filter(Product.id == product_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "PRODUCT_NOT_FOUND", "message": "product not found"})

    row.active = True
    db.flush()
    write_audit_log(db, entity_type="product", entity_id=row.id, action=AuditAction.UPDATE, after={"active": row.active})
    db.commit()
    db.refresh(row)
    return ProductResponse.model_validate(row)


@router.delete(
    "/{product_id}",
    status_code=204,
    responses={
        404: {"model": ApiErrorResponse, "description": "Not Found"},
        409: {"model": ApiErrorResponse, "description": "Conflict"},
        422: {"model": ApiErrorResponse, "description": "Validation Error"},
    },
)
def delete_product(product_id: int, db: Session = Depends(get_db)) -> Response:
    row = db.query(Product).filter(Product.id == product_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "PRODUCT_NOT_FOUND", "message": "product not found"})

    has_order_item_ref = db.query(OrderItem.id).filter(OrderItem.product_id == product_id).first() is not None
    has_supplier_map_ref = db.query(SupplierProduct.id).filter(SupplierProduct.product_id == product_id).first() is not None
    if has_order_item_ref or has_supplier_map_ref:
        raise HTTPException(status_code=409, detail={"code": "PRODUCT_IN_USE", "message": "product is referenced and cannot be deleted"})

    db.delete(row)
    db.flush()
    write_audit_log(db, entity_type="product", entity_id=product_id, action=AuditAction.CANCEL)
    db.commit()
    return Response(status_code=204)


def _bulk_response(total: int, success: int, errors: list[BulkOperationError]) -> ProductBulkOperationResponse:
    return ProductBulkOperationResponse(
        summary=BulkOperationSummary(total=total, success=success, failed=total - success),
        errors=errors,
    )


@router.post("/bulk/create", response_model=ProductBulkOperationResponse)
def bulk_create_products(payload: ProductBulkCreateRequest, db: Session = Depends(get_db)) -> ProductBulkOperationResponse:
    errors: list[BulkOperationError] = []
    success = 0

    for idx, item in enumerate(payload.items):
        exists = db.query(Product).filter(Product.sku == item.sku).first()
        if exists is not None:
            errors.append(BulkOperationError(index=idx, itemRef=item.sku, code="SKU_ALREADY_EXISTS", message="sku already exists"))
            continue

        row = Product(
            sku=item.sku,
            name=item.name,
            legacy_code=item.legacy_code,
            legacy_unit_code=item.legacy_unit_code,
            order_uom=item.order_uom,
            purchase_uom=item.purchase_uom,
            invoice_uom=item.invoice_uom,
            is_catch_weight=item.is_catch_weight,
            weight_capture_required=item.weight_capture_required,
            pricing_basis_default=item.pricing_basis_default,
            active=True,
        )
        db.add(row)
        db.flush()
        write_audit_log(db, entity_type="product", entity_id=row.id, action=AuditAction.CREATE)
        success += 1

    db.commit()
    return _bulk_response(total=len(payload.items), success=success, errors=errors)


@router.patch("/bulk/update", response_model=ProductBulkOperationResponse)
def bulk_update_products(payload: ProductBulkUpdateRequest, db: Session = Depends(get_db)) -> ProductBulkOperationResponse:
    errors: list[BulkOperationError] = []
    success = 0

    for idx, item in enumerate(payload.items):
        row = db.query(Product).filter(Product.id == item.id).first()
        if row is None:
            errors.append(BulkOperationError(index=idx, itemRef=str(item.id), code="PRODUCT_NOT_FOUND", message="product not found"))
            continue

        data = item.model_dump(exclude_unset=True)
        data.pop("id", None)
        for k, v in data.items():
            setattr(row, k, v)
        db.flush()
        write_audit_log(db, entity_type="product", entity_id=row.id, action=AuditAction.UPDATE)
        success += 1

    db.commit()
    return _bulk_response(total=len(payload.items), success=success, errors=errors)


@router.post("/bulk/upsert", response_model=ProductBulkOperationResponse)
def bulk_upsert_products(payload: ProductBulkUpsertRequest, db: Session = Depends(get_db)) -> ProductBulkOperationResponse:
    errors: list[BulkOperationError] = []
    success = 0

    for idx, item in enumerate(payload.items):
        row = db.query(Product).filter(Product.sku == item.sku).first()
        if row is None:
            row = Product(
                sku=item.sku,
                name=item.name,
                legacy_code=item.legacy_code,
                legacy_unit_code=item.legacy_unit_code,
                order_uom=item.order_uom,
                purchase_uom=item.purchase_uom,
                invoice_uom=item.invoice_uom,
                is_catch_weight=item.is_catch_weight,
                weight_capture_required=item.weight_capture_required,
                pricing_basis_default=item.pricing_basis_default,
                active=True,
            )
            db.add(row)
            db.flush()
            write_audit_log(db, entity_type="product", entity_id=row.id, action=AuditAction.CREATE)
            success += 1
            continue

        row.name = item.name
        row.legacy_code = item.legacy_code
        row.legacy_unit_code = item.legacy_unit_code
        row.order_uom = item.order_uom
        row.purchase_uom = item.purchase_uom
        row.invoice_uom = item.invoice_uom
        row.is_catch_weight = item.is_catch_weight
        row.weight_capture_required = item.weight_capture_required
        row.pricing_basis_default = item.pricing_basis_default
        db.flush()
        write_audit_log(db, entity_type="product", entity_id=row.id, action=AuditAction.UPDATE)
        success += 1

    db.commit()
    return _bulk_response(total=len(payload.items), success=success, errors=errors)


@router.post("/import-upsert", response_model=ProductImportResult)
def import_upsert_products(payload: ProductImportRequest, db: Session = Depends(get_db)) -> ProductImportResult:
    created = 0
    updated = 0
    skipped = 0
    errors: list[BulkOperationError] = []

    for idx, item in enumerate(payload.items):
        row = None
        item_ref = item.legacy_code or item.name

        if item.legacy_code:
            matches = db.query(Product).filter(Product.legacy_code == item.legacy_code).all()
            if len(matches) > 1:
                errors.append(BulkOperationError(index=idx, itemRef=item_ref, code="LEGACY_CODE_CONFLICT", message="multiple products have same legacy_code"))
                continue
            if len(matches) == 1:
                row = matches[0]

        if row is None:
            name_matches = db.query(Product).filter(Product.name == item.name).all()
            if len(name_matches) > 1:
                errors.append(BulkOperationError(index=idx, itemRef=item_ref, code="NAME_AMBIGUOUS", message="multiple products match by name"))
                continue
            if len(name_matches) == 1:
                row = name_matches[0]

        if row is None:
            sku = generate_next_code(db, Product, "sku", prefix="SKU-")
            row = Product(
                sku=sku,
                name=item.name,
                legacy_code=item.legacy_code,
                legacy_unit_code=item.legacy_unit_code,
                order_uom=item.order_uom,
                purchase_uom=item.purchase_uom,
                invoice_uom=item.invoice_uom,
                is_catch_weight=item.is_catch_weight,
                weight_capture_required=item.weight_capture_required,
                pricing_basis_default=item.pricing_basis_default,
                active=item.active,
            )
            db.add(row)
            db.flush()
            write_audit_log(db, entity_type="product", entity_id=row.id, action=AuditAction.CREATE)
            created += 1
            continue

        unchanged = (
            row.name == item.name
            and row.legacy_code == item.legacy_code
            and row.legacy_unit_code == item.legacy_unit_code
            and row.order_uom == item.order_uom
            and row.purchase_uom == item.purchase_uom
            and row.invoice_uom == item.invoice_uom
            and row.is_catch_weight == item.is_catch_weight
            and row.weight_capture_required == item.weight_capture_required
            and row.pricing_basis_default == item.pricing_basis_default
            and row.active == item.active
        )
        if unchanged:
            skipped += 1
            continue

        row.name = item.name
        row.legacy_code = item.legacy_code
        row.legacy_unit_code = item.legacy_unit_code
        row.order_uom = item.order_uom
        row.purchase_uom = item.purchase_uom
        row.invoice_uom = item.invoice_uom
        row.is_catch_weight = item.is_catch_weight
        row.weight_capture_required = item.weight_capture_required
        row.pricing_basis_default = item.pricing_basis_default
        row.active = item.active
        db.flush()
        write_audit_log(db, entity_type="product", entity_id=row.id, action=AuditAction.UPDATE)
        updated += 1

    db.commit()
    failed = len(errors)
    return ProductImportResult(total=len(payload.items), created=created, updated=updated, skipped=skipped, failed=failed, errors=errors)


@router.delete("/bulk/delete", response_model=ProductBulkOperationResponse)
def bulk_delete_products(payload: ProductBulkDeleteRequest, db: Session = Depends(get_db)) -> ProductBulkOperationResponse:
    errors: list[BulkOperationError] = []
    success = 0

    for idx, product_id in enumerate(payload.ids):
        row = db.query(Product).filter(Product.id == product_id).first()
        if row is None:
            errors.append(BulkOperationError(index=idx, itemRef=str(product_id), code="PRODUCT_NOT_FOUND", message="product not found"))
            continue
        db.delete(row)
        success += 1

    db.commit()
    return _bulk_response(total=len(payload.ids), success=success, errors=errors)
