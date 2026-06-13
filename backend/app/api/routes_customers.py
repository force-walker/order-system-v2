from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.audit import AuditAction, write_audit_log
from app.core.codegen import generate_next_code
from app.core.exception_mapping import map_integrity_error
from app.core.import_formats import CUSTOMER_IMPORT_FORMAT
from app.db.session import get_db
from app.models.entities import Customer, Order
from app.schemas.common import ApiErrorResponse, ImportFormatResponse
from app.schemas.customer import (
    CustomerCreateRequest,
    CustomerImportError,
    CustomerImportItem,
    CustomerImportRequest,
    CustomerImportResult,
    CustomerResponse,
    CustomerUpdateRequest,
)

router = APIRouter(prefix="/api/v1/customers", tags=["customers"])

CUSTOMER_COMMON_ERROR_RESPONSES = {
    422: {"model": ApiErrorResponse, "description": "Validation Error"},
}


@router.get("", response_model=list[CustomerResponse])
def list_customers(
    include_inactive: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> list[CustomerResponse]:
    query = db.query(Customer)
    if not include_inactive:
        query = query.filter(Customer.active.is_(True))
    rows = query.order_by(Customer.id.asc()).all()
    return [CustomerResponse.model_validate(r) for r in rows]


@router.get("/import-format", response_model=ImportFormatResponse)
def get_customer_import_format() -> ImportFormatResponse:
    return CUSTOMER_IMPORT_FORMAT


@router.get(
    "/{customer_id}",
    response_model=CustomerResponse,
    responses={**CUSTOMER_COMMON_ERROR_RESPONSES, 404: {"model": ApiErrorResponse, "description": "Not Found"}},
)
def get_customer(customer_id: int, db: Session = Depends(get_db)) -> CustomerResponse:
    row = db.query(Customer).filter(Customer.id == customer_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "CUSTOMER_NOT_FOUND", "message": "customer not found"})
    return CustomerResponse.model_validate(row)


@router.patch(
    "/{customer_id}",
    response_model=CustomerResponse,
    responses={**CUSTOMER_COMMON_ERROR_RESPONSES, 404: {"model": ApiErrorResponse, "description": "Not Found"}},
)
def update_customer(customer_id: int, payload: CustomerUpdateRequest, db: Session = Depends(get_db)) -> CustomerResponse:
    row = db.query(Customer).filter(Customer.id == customer_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "CUSTOMER_NOT_FOUND", "message": "customer not found"})

    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(row, k, v)

    db.flush()
    write_audit_log(db, entity_type="customer", entity_id=row.id, action=AuditAction.UPDATE)
    db.commit()
    db.refresh(row)
    return CustomerResponse.model_validate(row)


@router.post(
    "/{customer_id}/archive",
    response_model=CustomerResponse,
    responses={404: {"model": ApiErrorResponse, "description": "Not Found"}},
)
def archive_customer(customer_id: int, db: Session = Depends(get_db)) -> CustomerResponse:
    row = db.query(Customer).filter(Customer.id == customer_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "CUSTOMER_NOT_FOUND", "message": "customer not found"})

    row.active = False
    db.flush()
    write_audit_log(db, entity_type="customer", entity_id=row.id, action=AuditAction.UPDATE, after={"active": row.active})
    db.commit()
    db.refresh(row)
    return CustomerResponse.model_validate(row)


@router.post(
    "/{customer_id}/unarchive",
    response_model=CustomerResponse,
    responses={404: {"model": ApiErrorResponse, "description": "Not Found"}},
)
def unarchive_customer(customer_id: int, db: Session = Depends(get_db)) -> CustomerResponse:
    row = db.query(Customer).filter(Customer.id == customer_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "CUSTOMER_NOT_FOUND", "message": "customer not found"})

    row.active = True
    db.flush()
    write_audit_log(db, entity_type="customer", entity_id=row.id, action=AuditAction.UPDATE, after={"active": row.active})
    db.commit()
    db.refresh(row)
    return CustomerResponse.model_validate(row)


@router.delete(
    "/{customer_id}",
    status_code=204,
    responses={
        404: {"model": ApiErrorResponse, "description": "Not Found"},
        409: {"model": ApiErrorResponse, "description": "Conflict"},
        422: {"model": ApiErrorResponse, "description": "Validation Error"},
    },
)
def delete_customer(customer_id: int, db: Session = Depends(get_db)) -> Response:
    row = db.query(Customer).filter(Customer.id == customer_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "CUSTOMER_NOT_FOUND", "message": "customer not found"})

    has_order_ref = db.query(Order.id).filter(Order.customer_id == customer_id).first() is not None
    if has_order_ref:
        raise HTTPException(status_code=409, detail={"code": "CUSTOMER_IN_USE", "message": "customer is referenced and cannot be deleted"})

    db.delete(row)
    db.flush()
    write_audit_log(db, entity_type="customer", entity_id=customer_id, action=AuditAction.CANCEL)
    db.commit()
    return Response(status_code=204)


@router.post(
    "",
    response_model=CustomerResponse,
    status_code=201,
    responses={
        **CUSTOMER_COMMON_ERROR_RESPONSES,
        409: {"model": ApiErrorResponse, "description": "Conflict"},
    },
)
def create_customer(payload: CustomerCreateRequest, db: Session = Depends(get_db)) -> CustomerResponse:
    customer_code = generate_next_code(db, Customer, "customer_code", prefix="CUST-")

    exists = db.query(Customer).filter(Customer.customer_code == customer_code).first()
    if exists is not None:
        raise HTTPException(status_code=409, detail={"code": "CUSTOMER_CODE_ALREADY_EXISTS", "message": "customer code already exists"})

    row = Customer(customer_code=customer_code, region=payload.region, name=payload.name, active=payload.active)
    db.add(row)
    db.flush()
    write_audit_log(db, entity_type="customer", entity_id=row.id, action=AuditAction.CREATE)
    db.commit()
    db.refresh(row)
    return CustomerResponse.model_validate(row)


@router.post(
    "/import-upsert",
    response_model=CustomerImportResult,
    responses=CUSTOMER_COMMON_ERROR_RESPONSES,
)
def import_upsert_customers(payload: CustomerImportRequest, db: Session = Depends(get_db)) -> CustomerImportResult:
    created = 0
    updated = 0
    skipped = 0
    errors: list[CustomerImportError] = []

    seen_import_keys: set[str] = set()
    updatable_fields = {"import_key", "region", "name", "active"}

    def _append_row_error(
        *,
        idx: int,
        import_key: str | None,
        action: str,
        code: str,
        message: str,
        customer_id: int | None = None,
    ) -> None:
        errors.append(
            CustomerImportError(
                index=idx,
                import_key=import_key,
                action=action,
                code=code,
                message=message,
                customer_id=customer_id,
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
            item = CustomerImportItem.model_validate(normalized)
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
            target = db.query(Customer).filter(Customer.import_key == item.import_key).first()
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
                    customer_code = generate_next_code(db, Customer, "customer_code", prefix="CUST-")
                    row = Customer(
                        customer_code=customer_code,
                        import_key=item.import_key,
                        region=item.region,
                        name=item.name,
                        active=True if item.active is None else item.active,
                    )
                    db.add(row)
                    db.flush()
                    write_audit_log(db, entity_type="customer", entity_id=row.id, action=AuditAction.CREATE)
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
                write_audit_log(db, entity_type="customer", entity_id=target.id, action=AuditAction.UPDATE)
                updated += 1
        except IntegrityError as exc:
            _, code, message = map_integrity_error(exc)
            customer_id = target.id if target is not None else None
            _append_row_error(idx=idx, import_key=item.import_key, action=action, code=code, message=message, customer_id=customer_id)
            continue
        except SQLAlchemyError:
            customer_id = target.id if target is not None else None
            _append_row_error(
                idx=idx,
                import_key=item.import_key,
                action=action,
                code="DB_ERROR",
                message="database operation failed",
                customer_id=customer_id,
            )
            continue

    db.commit()
    return CustomerImportResult(
        total=len(payload.items),
        created=created,
        updated=updated,
        skipped=skipped,
        failed=len(errors),
        errors=errors,
    )
