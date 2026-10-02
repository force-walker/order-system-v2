from datetime import UTC, date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import asc, desc, func
from sqlalchemy.orm import Session

from app.core.audit import AuditAction, write_audit_log
from app.core.auth import AuthContext, get_auth_context
from app.core.purchase_completion import synchronize_order_purchase_status
from app.core.product_consistency import normalize_product_uom
from app.db.session import get_db
from app.models.entities import Customer, Order, OrderItem, PricingBasis, Product, PurchaseResult, Supplier, SupplierAllocation
from app.schemas.common import ApiErrorResponse
from app.schemas.purchase_result import (
    PurchaseResultBulkUpsertRequest,
    PurchaseResultBulkUpsertResponse,
    PurchaseResultCreateRequest,
    PurchaseResultDeferRequest,
    PurchaseResultResponse,
    PurchaseResultUpdateRequest,
)

router = APIRouter(prefix="/api/v1/purchase-results", tags=["purchase-results"])

PURCHASE_RESULT_COMMON_ERROR_RESPONSES = {
    422: {"model": ApiErrorResponse, "description": "Validation Error"},
}


def _get_allocation_or_404(db: Session, allocation_id: int) -> SupplierAllocation:
    alloc = db.query(SupplierAllocation).filter(SupplierAllocation.id == allocation_id).with_for_update().first()
    if alloc is None:
        raise HTTPException(status_code=404, detail={"code": "ALLOCATION_NOT_FOUND", "message": "allocation not found"})
    return alloc


PURCHASE_RESULT_EDITABLE_FIELDS = (
    "supplier_id", "purchased_qty", "purchased_uom", "actual_weight_kg", "unit_cost", "final_unit_cost",
    "shortage_qty", "shortage_policy", "result_status", "invoiceable_flag", "recorded_by", "note",
)


def _comparable(field: str, value):
    if hasattr(value, "value"):
        return value.value
    if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
        return Decimal(str(value))
    if field == "purchased_uom" and isinstance(value, str):
        return normalize_product_uom(value)
    return value


def _purchase_result_snapshot(row: PurchaseResult) -> dict:
    snapshot: dict = {}
    for field in PURCHASE_RESULT_EDITABLE_FIELDS:
        value = getattr(row, field)
        if hasattr(value, "value"):
            value = value.value
        elif isinstance(value, Decimal):
            value = float(value)
        snapshot[field] = value
    return snapshot


def _is_purchase_result_unchanged(row: PurchaseResult, desired: dict) -> bool:
    return all(_comparable(field, getattr(row, field)) == _comparable(field, value) for field, value in desired.items())


def _default_supplier_id(payload_supplier_id: int | None, alloc: SupplierAllocation) -> int | None:
    if payload_supplier_id is not None:
        return payload_supplier_id
    if alloc.final_supplier_id is not None:
        return alloc.final_supplier_id
    return alloc.suggested_supplier_id


def _get_product_for_allocation(db: Session, alloc: SupplierAllocation) -> Product:
    product = (
        db.query(Product)
        .join(OrderItem, OrderItem.product_id == Product.id)
        .filter(OrderItem.id == alloc.order_item_id)
        .first()
    )
    if product is None:
        raise HTTPException(status_code=404, detail={"code": "PRODUCT_NOT_FOUND", "message": "allocation product not found"})
    return product


def _lock_and_sync_purchase_order(db: Session, alloc: SupplierAllocation, *, actor: str | None = None) -> None:
    item = db.query(OrderItem).filter(OrderItem.id == alloc.order_item_id).first()
    if item is None:
        return
    order = db.query(Order).filter(Order.id == item.order_id).with_for_update().first()
    if order is not None:
        synchronize_order_purchase_status(db, order, actor=actor)


def _validate_purchase_uom(db: Session, *, alloc: SupplierAllocation, purchased_uom: str) -> Product:
    product = _get_product_for_allocation(db, alloc)
    actual = normalize_product_uom(purchased_uom)
    expected = normalize_product_uom(product.purchase_uom)
    allocation_uom = normalize_product_uom(alloc.final_uom)
    if actual != expected or allocation_uom != expected:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "PURCHASE_UOM_MISMATCH",
                "message": "purchased_uom must match product.purchase_uom and allocation.final_uom",
                "details": [{"purchased_uom": purchased_uom, "purchase_uom": product.purchase_uom, "allocation_uom": alloc.final_uom}],
            },
        )
    return product


def _validate_actual_weight_required(
    db: Session,
    *,
    alloc: SupplierAllocation,
    actual_weight_kg: float | None,
) -> None:
    row = (
        db.query(OrderItem, Product)
        .join(Product, Product.id == OrderItem.product_id)
        .filter(OrderItem.id == alloc.order_item_id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "PRODUCT_NOT_FOUND", "message": "allocation product not found"})
    item, product = row
    requires_weight = product.is_catch_weight or product.weight_capture_required or item.pricing_basis == PricingBasis.uom_kg
    if requires_weight and actual_weight_kg is None:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "ACTUAL_WEIGHT_REQUIRED",
                "message": "actual_weight_kg is required for catch-weight or uom_kg purchase results",
            },
        )


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


def _to_purchase_result_response(db: Session, row: PurchaseResult) -> PurchaseResultResponse:
    alloc = db.query(SupplierAllocation).filter(SupplierAllocation.id == row.allocation_id).first()

    product_id = None
    product_name = None
    invoice_uom = None
    order_uom = row.purchased_uom
    purchase_uom = row.purchased_uom
    order_id = None
    customer_id = None
    customer_name = None

    if alloc is not None:
        order_item = db.query(OrderItem).filter(OrderItem.id == alloc.order_item_id).first()
        if order_item is not None:
            product = db.query(Product).filter(Product.id == order_item.product_id).first()
            if product is not None:
                product_id = product.id
                product_name = product.name
                order_uom = product.order_uom
                purchase_uom = product.purchase_uom
                invoice_uom = product.invoice_uom

            order = db.query(Order).filter(Order.id == order_item.order_id).first()
            if order is not None:
                order_id = order.id
                customer = db.query(Customer).filter(Customer.id == order.customer_id).first()
                if customer is not None:
                    customer_id = customer.id
                    customer_name = customer.name

    supplier_name = None
    if row.supplier_id is not None:
        supplier = db.query(Supplier).filter(Supplier.id == row.supplier_id).first()
        if supplier is not None:
            supplier_name = supplier.name

    return PurchaseResultResponse(
        id=row.id,
        allocation_id=row.allocation_id,
        order_id=order_id,
        supplier_id=row.supplier_id,
        supplier_name=supplier_name,
        purchased_qty=float(row.purchased_qty),
        purchased_uom=row.purchased_uom,
        received_qty=float(row.purchased_qty),
        order_uom=order_uom,
        purchase_uom=purchase_uom,
        invoice_qty=float(row.invoice_qty) if row.invoice_qty is not None else None,
        invoice_uom=invoice_uom,
        customer_id=customer_id,
        customer_name=customer_name,
        product_id=product_id,
        product_name=product_name,
        actual_weight_kg=float(row.actual_weight_kg) if row.actual_weight_kg is not None else None,
        unit_cost=float(row.unit_cost) if row.unit_cost is not None else None,
        final_unit_cost=float(row.final_unit_cost) if row.final_unit_cost is not None else None,
        shortage_qty=float(row.shortage_qty) if row.shortage_qty is not None else None,
        shortage_policy=row.shortage_policy,
        result_status=row.result_status,
        invoiceable_flag=row.invoiceable_flag,
        recorded_by=row.recorded_by,
        recorded_at=row.recorded_at,
        note=row.note,
        is_deferred=row.is_deferred,
        defer_until=row.defer_until,
        defer_reason=row.defer_reason,
        deferred_by=row.deferred_by,
        deferred_at=row.deferred_at,
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
    _validate_purchase_uom(db, alloc=alloc, purchased_uom=payload.purchased_uom)
    _validate_actual_weight_required(db, alloc=alloc, actual_weight_kg=payload.actual_weight_kg)
    _validate_quantity_limit(db, alloc=alloc, incoming_qty=payload.purchased_qty)

    row = PurchaseResult(
        **payload.model_dump(exclude={"supplier_id"}),
        supplier_id=_default_supplier_id(payload.supplier_id, alloc),
    )
    db.add(row)
    db.flush()
    write_audit_log(db, entity_type="purchase_result", entity_id=row.id, action=AuditAction.CREATE)
    _lock_and_sync_purchase_order(db, alloc)
    db.commit()
    db.refresh(row)
    return _to_purchase_result_response(db, row)


@router.get(
    "/{result_id}",
    response_model=PurchaseResultResponse,
    responses={404: {"model": ApiErrorResponse, "description": "Not Found"}},
)
def get_purchase_result(result_id: int, db: Session = Depends(get_db)) -> PurchaseResultResponse:
    row = db.query(PurchaseResult).filter(PurchaseResult.id == result_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "RESOURCE_NOT_FOUND", "message": "purchase result not found"})
    return _to_purchase_result_response(db, row)


@router.get(
    "",
    response_model=list[PurchaseResultResponse],
    responses={**PURCHASE_RESULT_COMMON_ERROR_RESPONSES, 404: {"model": ApiErrorResponse, "description": "Not Found"}},
)
def list_purchase_results(
    allocation_id: int | None = Query(default=None, gt=0),
    customer_id: int | None = Query(default=None, gt=0),
    product_id: int | None = Query(default=None, gt=0),
    supplier_id: int | None = Query(default=None, gt=0),
    sort_by: str = Query(default="recorded_at"),
    sort_order: str = Query(default="asc"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[PurchaseResultResponse]:
    query = (
        db.query(PurchaseResult)
        .join(SupplierAllocation, SupplierAllocation.id == PurchaseResult.allocation_id)
        .join(OrderItem, OrderItem.id == SupplierAllocation.order_item_id)
        .join(Order, Order.id == OrderItem.order_id)
        .join(Product, Product.id == OrderItem.product_id)
        .join(Customer, Customer.id == Order.customer_id)
        .outerjoin(Supplier, Supplier.id == PurchaseResult.supplier_id)
    )

    if allocation_id is not None:
        _get_allocation_or_404(db, allocation_id)
        query = query.filter(PurchaseResult.allocation_id == allocation_id)
    if customer_id is not None:
        query = query.filter(Customer.id == customer_id)
    if product_id is not None:
        query = query.filter(Product.id == product_id)
    if supplier_id is not None:
        query = query.filter(PurchaseResult.supplier_id == supplier_id)

    sort_map = {
        "recorded_at": PurchaseResult.recorded_at,
        "customer": Customer.name,
        "product": Product.name,
        "supplier": Supplier.name,
    }
    sort_col = sort_map.get(sort_by)
    if sort_col is None:
        raise HTTPException(status_code=422, detail={"code": "VALIDATION_ERROR", "message": "invalid sort_by"})

    order_func = desc if sort_order == "desc" else asc
    if sort_order not in {"asc", "desc"}:
        raise HTTPException(status_code=422, detail={"code": "VALIDATION_ERROR", "message": "invalid sort_order"})

    rows = query.order_by(order_func(sort_col), PurchaseResult.id.asc()).offset(offset).limit(limit).all()
    return [_to_purchase_result_response(db, row) for row in rows]


@router.get(
    "/queue/work-queue",
    response_model=list[PurchaseResultResponse],
    responses={**PURCHASE_RESULT_COMMON_ERROR_RESPONSES},
)
def list_purchase_result_work_queue(
    target_date: date | None = Query(default=None),
    customer_id: int | None = Query(default=None, gt=0),
    product_id: int | None = Query(default=None, gt=0),
    supplier_id: int | None = Query(default=None, gt=0),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[PurchaseResultResponse]:
    day = target_date or date.today()
    now = datetime.now(UTC)

    query = (
        db.query(PurchaseResult)
        .join(SupplierAllocation, SupplierAllocation.id == PurchaseResult.allocation_id)
        .join(OrderItem, OrderItem.id == SupplierAllocation.order_item_id)
        .join(Order, Order.id == OrderItem.order_id)
        .join(Product, Product.id == OrderItem.product_id)
        .join(Customer, Customer.id == Order.customer_id)
        .outerjoin(Supplier, Supplier.id == PurchaseResult.supplier_id)
        .filter(PurchaseResult.invoiceable_flag.is_(True))
        .filter(func.date(PurchaseResult.recorded_at) == day)
        .filter((PurchaseResult.is_deferred.is_(False)) | ((PurchaseResult.defer_until.is_not(None)) & (PurchaseResult.defer_until <= now)))
    )

    if customer_id is not None:
        query = query.filter(Customer.id == customer_id)
    if product_id is not None:
        query = query.filter(Product.id == product_id)
    if supplier_id is not None:
        query = query.filter(PurchaseResult.supplier_id == supplier_id)

    rows = query.order_by(PurchaseResult.recorded_at.asc(), PurchaseResult.id.asc()).offset(offset).limit(limit).all()
    return [_to_purchase_result_response(db, row) for row in rows]


@router.get(
    "/queue/history",
    response_model=list[PurchaseResultResponse],
    responses={**PURCHASE_RESULT_COMMON_ERROR_RESPONSES},
)
def list_purchase_result_history(
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    customer_id: int | None = Query(default=None, gt=0),
    product_id: int | None = Query(default=None, gt=0),
    supplier_id: int | None = Query(default=None, gt=0),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[PurchaseResultResponse]:
    query = (
        db.query(PurchaseResult)
        .join(SupplierAllocation, SupplierAllocation.id == PurchaseResult.allocation_id)
        .join(OrderItem, OrderItem.id == SupplierAllocation.order_item_id)
        .join(Order, Order.id == OrderItem.order_id)
        .join(Product, Product.id == OrderItem.product_id)
        .join(Customer, Customer.id == Order.customer_id)
        .outerjoin(Supplier, Supplier.id == PurchaseResult.supplier_id)
    )

    if from_date is not None:
        query = query.filter(func.date(PurchaseResult.recorded_at) >= from_date)
    if to_date is not None:
        query = query.filter(func.date(PurchaseResult.recorded_at) <= to_date)
    if customer_id is not None:
        query = query.filter(Customer.id == customer_id)
    if product_id is not None:
        query = query.filter(Product.id == product_id)
    if supplier_id is not None:
        query = query.filter(PurchaseResult.supplier_id == supplier_id)

    rows = query.order_by(PurchaseResult.recorded_at.desc(), PurchaseResult.id.desc()).offset(offset).limit(limit).all()
    return [_to_purchase_result_response(db, row) for row in rows]


@router.patch(
    "/{result_id}",
    response_model=PurchaseResultResponse,
    responses={**PURCHASE_RESULT_COMMON_ERROR_RESPONSES, 404: {"model": ApiErrorResponse, "description": "Not Found"}},
)
def update_purchase_result(
    result_id: int,
    payload: PurchaseResultUpdateRequest,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> PurchaseResultResponse:
    row = db.query(PurchaseResult).filter(PurchaseResult.id == result_id).with_for_update().first()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "RESOURCE_NOT_FOUND", "message": "purchase result not found"})
    data = payload.model_dump(exclude_unset=True)
    alloc = _get_allocation_or_404(db, row.allocation_id)
    if "supplier_id" in data and data["supplier_id"] is None:
        data["supplier_id"] = _default_supplier_id(None, alloc)
    if _is_purchase_result_unchanged(row, data):
        return _to_purchase_result_response(db, row)
    if row.invoice_qty is not None:
        raise HTTPException(
            status_code=409,
            detail={"code": "PURCHASE_RESULT_ALREADY_CLAIMED", "message": "claimed purchase result cannot be edited"},
        )

    before = _purchase_result_snapshot(row)
    for k, v in data.items():
        setattr(row, k, v)

    _validate_purchase_uom(db, alloc=alloc, purchased_uom=row.purchased_uom)
    _validate_actual_weight_required(db, alloc=alloc, actual_weight_kg=row.actual_weight_kg)
    _validate_quantity_limit(db, alloc=alloc, incoming_qty=row.purchased_qty, exclude_result_id=row.id)

    if row.supplier_id is None:
        row.supplier_id = _default_supplier_id(None, alloc)

    db.flush()
    write_audit_log(db, entity_type="purchase_result", entity_id=row.id, action=AuditAction.UPDATE, actor=auth.user_id, before=before, after=_purchase_result_snapshot(row))
    _lock_and_sync_purchase_order(db, alloc, actor=auth.user_id)
    db.commit()
    db.refresh(row)
    return _to_purchase_result_response(db, row)


@router.post(
    "/{result_id}/defer",
    response_model=PurchaseResultResponse,
    responses={**PURCHASE_RESULT_COMMON_ERROR_RESPONSES, 404: {"model": ApiErrorResponse, "description": "Not Found"}},
)
def defer_purchase_result(result_id: int, payload: PurchaseResultDeferRequest, db: Session = Depends(get_db)) -> PurchaseResultResponse:
    row = db.query(PurchaseResult).filter(PurchaseResult.id == result_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "RESOURCE_NOT_FOUND", "message": "purchase result not found"})

    row.is_deferred = True
    row.defer_until = payload.defer_until
    row.defer_reason = payload.defer_reason
    row.deferred_by = payload.deferred_by
    row.deferred_at = datetime.now(UTC)

    db.flush()
    write_audit_log(db, entity_type="purchase_result", entity_id=row.id, action=AuditAction.UPDATE)
    db.commit()
    db.refresh(row)
    return _to_purchase_result_response(db, row)


@router.post(
    "/{result_id}/undefer",
    response_model=PurchaseResultResponse,
    responses={**PURCHASE_RESULT_COMMON_ERROR_RESPONSES, 404: {"model": ApiErrorResponse, "description": "Not Found"}},
)
def undefer_purchase_result(result_id: int, db: Session = Depends(get_db)) -> PurchaseResultResponse:
    row = db.query(PurchaseResult).filter(PurchaseResult.id == result_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "RESOURCE_NOT_FOUND", "message": "purchase result not found"})

    row.is_deferred = False
    row.defer_until = None
    row.defer_reason = None
    row.deferred_by = None
    row.deferred_at = None

    db.flush()
    write_audit_log(db, entity_type="purchase_result", entity_id=row.id, action=AuditAction.UPDATE)
    db.commit()
    db.refresh(row)
    return _to_purchase_result_response(db, row)


@router.post(
    "/bulk-upsert",
    response_model=PurchaseResultBulkUpsertResponse,
    responses={**PURCHASE_RESULT_COMMON_ERROR_RESPONSES, 404: {"model": ApiErrorResponse, "description": "Not Found"}},
)
def bulk_upsert_purchase_results(
    payload: PurchaseResultBulkUpsertRequest,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
) -> PurchaseResultBulkUpsertResponse:
    count = 0
    result_ids: list[int] = []
    touched_allocations: dict[int, SupplierAllocation] = {}
    for item in payload.items:
        alloc = _get_allocation_or_404(db, item.allocation_id)
        touched_allocations[alloc.id] = alloc
        _validate_purchase_uom(db, alloc=alloc, purchased_uom=item.purchased_uom)
        _validate_actual_weight_required(db, alloc=alloc, actual_weight_kg=item.actual_weight_kg)

        row = db.query(PurchaseResult).filter(PurchaseResult.allocation_id == item.allocation_id).with_for_update().first()
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
            desired = item.model_dump(exclude={"allocation_id"})
            desired["supplier_id"] = _default_supplier_id(item.supplier_id, alloc)
            if _is_purchase_result_unchanged(row, desired):
                count += 1
                result_ids.append(row.id)
                continue
            if row.invoice_qty is not None:
                raise HTTPException(
                    status_code=409,
                    detail={"code": "PURCHASE_RESULT_ALREADY_CLAIMED", "message": "claimed purchase result cannot be edited"},
                )
            before = _purchase_result_snapshot(row)
            for k, v in desired.items():
                setattr(row, k, v)
            if row.supplier_id is None:
                row.supplier_id = _default_supplier_id(None, alloc)
            _validate_quantity_limit(db, alloc=alloc, incoming_qty=row.purchased_qty, exclude_result_id=row.id)
            db.flush()
            write_audit_log(db, entity_type="purchase_result", entity_id=row.id, action=AuditAction.BULK_UPSERT_UPDATE, actor=auth.user_id, before=before, after=_purchase_result_snapshot(row))
        count += 1
        result_ids.append(row.id)

    touched_order_ids: set[str] = set()
    for alloc in touched_allocations.values():
        order_item = db.query(OrderItem).filter(OrderItem.id == alloc.order_item_id).first()
        if order_item is not None:
            touched_order_ids.add(order_item.order_id)
    locked_orders = (
        db.query(Order)
        .filter(Order.id.in_(sorted(touched_order_ids)))
        .order_by(Order.id.asc())
        .with_for_update()
        .all()
        if touched_order_ids
        else []
    )
    for order in locked_orders:
        synchronize_order_purchase_status(db, order, actor=auth.user_id)

    db.commit()
    return PurchaseResultBulkUpsertResponse(upserted_count=count, purchase_result_ids=result_ids)
