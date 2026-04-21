from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import asc, desc
from sqlalchemy.orm import Session

from app.core.audit import AuditAction, write_audit_log
from app.db.session import get_db
from app.models.entities import Customer, Order, OrderItem, Product, PurchaseResult, Supplier, SupplierAllocation
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


def _to_purchase_result_response(db: Session, row: PurchaseResult) -> PurchaseResultResponse:
    joined = (
        db.query(
            Supplier.name.label("supplier_name"),
            Product.id.label("product_id"),
            Product.name.label("product_name"),
            Product.invoice_uom.label("invoice_uom"),
            Customer.id.label("customer_id"),
            Customer.name.label("customer_name"),
        )
        .join(SupplierAllocation, SupplierAllocation.id == row.allocation_id)
        .join(OrderItem, OrderItem.id == SupplierAllocation.order_item_id)
        .join(Product, Product.id == OrderItem.product_id)
        .join(Order, Order.id == OrderItem.order_id)
        .join(Customer, Customer.id == Order.customer_id)
        .outerjoin(Supplier, Supplier.id == row.supplier_id)
        .first()
    )

    return PurchaseResultResponse(
        id=row.id,
        allocation_id=row.allocation_id,
        supplier_id=row.supplier_id,
        supplier_name=joined.supplier_name if joined else None,
        purchased_qty=float(row.purchased_qty),
        purchased_uom=row.purchased_uom,
        received_qty=float(row.purchased_qty),
        order_uom=row.purchased_uom,
        invoice_qty=None,
        invoice_uom=joined.invoice_uom if joined else None,
        customer_id=joined.customer_id if joined else None,
        customer_name=joined.customer_name if joined else None,
        product_id=joined.product_id if joined else None,
        product_name=joined.product_name if joined else None,
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
    return _to_purchase_result_response(db, row)


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
