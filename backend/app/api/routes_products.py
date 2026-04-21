from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.exception_mapping import map_integrity_error

from app.core.audit import AuditAction, write_audit_log
from app.core.codegen import generate_next_code
from app.db.session import get_db
from app.models.entities import OrderItem, PricingBasis, Product, SupplierProduct
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
    ProductImportError,
    ProductImportItem,
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
        category_code=payload.category_code,
        product_type_code=payload.product_type_code,
        name_kana=payload.name_kana,
        name_kana_key=payload.name_kana_key,
        legacy_unit_code=payload.legacy_unit_code,
        pack_size=payload.pack_size,
        tax_category_code=payload.tax_category_code,
        inventory_category_code=payload.inventory_category_code,
        owner_code=payload.owner_code,
        origin_code=payload.origin_code,
        jan_code=payload.jan_code,
        sales_price=payload.sales_price,
        sales_price_1=payload.sales_price_1,
        sales_price_2=payload.sales_price_2,
        sales_price_3=payload.sales_price_3,
        sales_price_4=payload.sales_price_4,
        sales_price_5=payload.sales_price_5,
        sales_price_6=payload.sales_price_6,
        purchase_price=payload.purchase_price,
        inventory_price=payload.inventory_price,
        list_price=payload.list_price,
        tax_rate_code=payload.tax_rate_code,
        handling_category_code=payload.handling_category_code,
        name_en=payload.name_en,
        name_zh_hk=payload.name_zh_hk,
        customs_reference_price=payload.customs_reference_price,
        customs_origin_text=payload.customs_origin_text,
        remarks=payload.remarks,
        chayafuda_flag=payload.chayafuda_flag,
        application_category_code=payload.application_category_code,
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
    errors: list[ProductImportError] = []

    seen_import_keys: set[str] = set()

    def _append_row_error(
        *,
        idx: int,
        import_key: str | None,
        action: str,
        code: str,
        message: str,
        product_id: int | None = None,
    ) -> None:
        errors.append(
            ProductImportError(
                index=idx,
                import_key=import_key,
                action=action,
                code=code,
                message=message,
                product_id=product_id,
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

    updatable_fields = {
        "import_key",
        "legacy_code",
        "category_code",
        "product_type_code",
        "name",
        "name_kana",
        "name_kana_key",
        "legacy_unit_code",
        "pack_size",
        "tax_category_code",
        "inventory_category_code",
        "owner_code",
        "origin_code",
        "jan_code",
        "sales_price",
        "sales_price_1",
        "sales_price_2",
        "sales_price_3",
        "sales_price_4",
        "sales_price_5",
        "sales_price_6",
        "purchase_price",
        "inventory_price",
        "list_price",
        "tax_rate_code",
        "handling_category_code",
        "name_en",
        "name_zh_hk",
        "customs_reference_price",
        "customs_origin_text",
        "remarks",
        "chayafuda_flag",
        "application_category_code",
        "order_uom",
        "purchase_uom",
        "invoice_uom",
        "is_catch_weight",
        "weight_capture_required",
        "pricing_basis_default",
        "active",
    }

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
            item = ProductImportItem.model_validate(normalized)
        except ValidationError as exc:
            detail_rows = []
            for err in exc.errors():
                loc = ".".join(str(part) for part in err.get("loc", []))
                msg = err.get("msg", "invalid value")
                detail_rows.append(f"{loc}: {msg}" if loc else msg)
            message = "; ".join(detail_rows) if detail_rows else "invalid import item"
            _append_row_error(
                idx=idx,
                import_key=import_key,
                action="create",
                code="ITEM_VALIDATION_ERROR",
                message=message,
            )
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
            target = db.query(Product).filter(Product.import_key == item.import_key).first()
            if target is not None:
                action = "update"

        if action == "create":
            required_missing = [
                name
                for name in ("name", "order_uom", "purchase_uom", "invoice_uom")
                if getattr(item, name) is None
            ]
            if required_missing:
                _append_row_error(
                    idx=idx,
                    import_key=item.import_key,
                    action="create",
                    code="REQUIRED_FIELDS_MISSING",
                    message=f"missing required fields for create: {', '.join(required_missing)}",
                )
                continue

        try:
            with db.begin_nested():
                if action == "create":
                    sku = generate_next_code(db, Product, "sku", prefix="SKU-")
                    row = Product(
                        sku=sku,
                        import_key=item.import_key,
                        legacy_code=item.legacy_code,
                        category_code=item.category_code,
                        product_type_code=item.product_type_code,
                        name=item.name,
                        name_kana=item.name_kana,
                        name_kana_key=item.name_kana_key,
                        legacy_unit_code=item.legacy_unit_code,
                        pack_size=item.pack_size,
                        tax_category_code=item.tax_category_code,
                        inventory_category_code=item.inventory_category_code,
                        owner_code=item.owner_code,
                        origin_code=item.origin_code,
                        jan_code=item.jan_code,
                        sales_price=item.sales_price,
                        sales_price_1=item.sales_price_1,
                        sales_price_2=item.sales_price_2,
                        sales_price_3=item.sales_price_3,
                        sales_price_4=item.sales_price_4,
                        sales_price_5=item.sales_price_5,
                        sales_price_6=item.sales_price_6,
                        purchase_price=item.purchase_price,
                        inventory_price=item.inventory_price,
                        list_price=item.list_price,
                        tax_rate_code=item.tax_rate_code,
                        handling_category_code=item.handling_category_code,
                        name_en=item.name_en,
                        name_zh_hk=item.name_zh_hk,
                        customs_reference_price=item.customs_reference_price,
                        customs_origin_text=item.customs_origin_text,
                        remarks=item.remarks,
                        chayafuda_flag=item.chayafuda_flag,
                        application_category_code=item.application_category_code,
                        order_uom=item.order_uom,
                        purchase_uom=item.purchase_uom,
                        invoice_uom=item.invoice_uom,
                        is_catch_weight=item.is_catch_weight if item.is_catch_weight is not None else False,
                        weight_capture_required=item.weight_capture_required if item.weight_capture_required is not None else False,
                        pricing_basis_default=item.pricing_basis_default or PricingBasis.uom_count,
                        active=True if item.active is None else item.active,
                    )
                    db.add(row)
                    db.flush()
                    write_audit_log(db, entity_type="product", entity_id=row.id, action=AuditAction.CREATE)
                    created += 1
                    continue

                changed = False
                for field, value in normalized.items():
                    if field not in updatable_fields or field == "sku":
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
                write_audit_log(db, entity_type="product", entity_id=target.id, action=AuditAction.UPDATE)
                updated += 1
        except IntegrityError as exc:
            _, code, message = map_integrity_error(exc)
            product_id = target.id if target is not None else None
            _append_row_error(idx=idx, import_key=item.import_key, action=action, code=code, message=message, product_id=product_id)
            continue
        except SQLAlchemyError:
            product_id = target.id if target is not None else None
            _append_row_error(
                idx=idx,
                import_key=item.import_key,
                action=action,
                code="DB_ERROR",
                message="database operation failed",
                product_id=product_id,
            )
            continue

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
