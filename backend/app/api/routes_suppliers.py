from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import ValidationError
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.audit import AuditAction, write_audit_log
from app.core.codegen import generate_next_code
from app.core.exception_mapping import map_integrity_error
from app.db.session import get_db
from app.models.entities import Product, PurchaseResult, Supplier, SupplierAllocation, SupplierProduct
from app.schemas.common import ApiErrorResponse
from app.schemas.supplier import (
    SupplierCreateRequest,
    SupplierImportError,
    SupplierImportItem,
    SupplierImportRequest,
    SupplierImportResult,
    SupplierResponse,
    SupplierUpdateRequest,
)
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


@router.post(
    "/import-upsert",
    response_model=SupplierImportResult,
    responses=SUPPLIER_COMMON_ERROR_RESPONSES,
)
def import_upsert_suppliers(payload: SupplierImportRequest, db: Session = Depends(get_db)) -> SupplierImportResult:
    created = 0
    updated = 0
    skipped = 0
    errors: list[SupplierImportError] = []

    seen_import_keys: set[str] = set()
    updatable_fields = {"import_key", "name", "active"}

    def _append_row_error(
        *,
        idx: int,
        import_key: str | None,
        action: str,
        code: str,
        message: str,
        supplier_id: int | None = None,
    ) -> None:
        errors.append(
            SupplierImportError(
                index=idx,
                import_key=import_key,
                action=action,
                code=code,
                message=message,
                supplier_id=supplier_id,
            )
        )

    def _normalize_raw_item(raw_item: dict) -> dict:
        normalized = {}
        for k, v in raw_item.items():
            if isinstance(v, str) and v.strip() == "":
                normalized[k] = None
            else:
                normalized[k] = v
        return normalized

    for idx, raw_item in enumerate(payload.items):
        if not isinstance(raw_item, dict):
            _append_row_error(idx=idx, import_key=None, action="create", code="ITEM_VALIDATION_ERROR", message="item must be an object")
            continue

        normalized = _normalize_raw_item(raw_item)
        import_key = normalized.get("import_key")
        if import_key is not None and not isinstance(import_key, str):
            _append_row_error(idx=idx, import_key=None, action="create", code="ITEM_VALIDATION_ERROR", message="import_key must be a string")
            continue

        try:
            item = SupplierImportItem.model_validate(normalized)
        except ValidationError as exc:
            detail_rows = []
            for err in exc.errors():
                loc = ".".join(str(part) for part in err.get("loc", []))
                msg = err.get("msg", "invalid value")
                detail_rows.append(f"{loc}: {msg}" if loc else msg)
            message = "; ".join(detail_rows) if detail_rows else "invalid import item"
            _append_row_error(idx=idx, import_key=import_key, action="create", code="ITEM_VALIDATION_ERROR", message=message)
            continue

        if item.import_key:
            if item.import_key in seen_import_keys:
                _append_row_error(
                    idx=idx,
                    import_key=item.import_key,
                    action="create",
                    code="DUPLICATE_IMPORT_KEY_IN_PAYLOAD",
                    message="import_key duplicated in import payload",
                )
                continue
            seen_import_keys.add(item.import_key)

        target = None
        action = "create"
        if item.import_key:
            target = db.query(Supplier).filter(Supplier.import_key == item.import_key).first()
            if target is not None:
                action = "update"

        if action == "create" and item.name is None:
            _append_row_error(
                idx=idx,
                import_key=item.import_key,
                action="create",
                code="REQUIRED_FIELDS_MISSING",
                message="missing required fields for create: name",
            )
            continue

        try:
            with db.begin_nested():
                if action == "create":
                    supplier_code = generate_next_code(db, Supplier, "supplier_code", prefix="SUP-")
                    row = Supplier(
                        supplier_code=supplier_code,
                        import_key=item.import_key,
                        name=item.name,
                        active=True if item.active is None else item.active,
                    )
                    db.add(row)
                    db.flush()
                    write_audit_log(db, entity_type="supplier", entity_id=row.id, action=AuditAction.CREATE)
                    created += 1
                    continue

                changed = False
                for field, value in normalized.items():
                    if field not in updatable_fields:
                        continue
                    if value is None:
                        continue
                    if getattr(target, field) != value:
                        setattr(target, field, value)
                        changed = True

                if not changed:
                    skipped += 1
                    continue

                db.flush()
                write_audit_log(db, entity_type="supplier", entity_id=target.id, action=AuditAction.UPDATE)
                updated += 1
        except IntegrityError as exc:
            _, code, message = map_integrity_error(exc)
            supplier_id = target.id if target is not None else None
            _append_row_error(idx=idx, import_key=item.import_key, action=action, code=code, message=message, supplier_id=supplier_id)
            continue
        except SQLAlchemyError:
            supplier_id = target.id if target is not None else None
            _append_row_error(
                idx=idx,
                import_key=item.import_key,
                action=action,
                code="DB_ERROR",
                message="database operation failed",
                supplier_id=supplier_id,
            )
            continue

    db.commit()
    return SupplierImportResult(
        total=len(payload.items),
        created=created,
        updated=updated,
        skipped=skipped,
        failed=len(errors),
        errors=errors,
    )


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
