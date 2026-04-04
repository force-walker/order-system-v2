from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.audit import AuditAction, write_audit_log
from app.db.session import get_db
from app.models.entities import Customer, LineStatus, Order, OrderItem, OrderStatus, PricingBasis, Product
from app.schemas.common import ApiErrorResponse
from app.schemas.order import (
    OrderBulkTransitionRequest,
    OrderBulkTransitionResponse,
    OrderCreateRequest,
    OrderUpdateRequest,
    OrderItemCreateRequest,
    OrderItemResponse,
    OrderItemsBulkCreateRequest,
    OrderItemsBulkCreateResponse,
    OrderItemUpdateRequest,
    OrderResponse,
)

router = APIRouter(prefix="/api/v1/orders", tags=["orders"])

ORDER_COMMON_ERROR_RESPONSES = {
    422: {"model": ApiErrorResponse, "description": "Validation Error"},
}


@router.get("", response_model=list[OrderResponse])
def list_orders(db: Session = Depends(get_db)) -> list[OrderResponse]:
    rows = db.query(Order).order_by(Order.id.desc()).all()
    return [OrderResponse.model_validate(r) for r in rows]


@router.get(
    "/{order_id}",
    response_model=OrderResponse,
    responses={**ORDER_COMMON_ERROR_RESPONSES, 404: {"model": ApiErrorResponse, "description": "Not Found"}},
)
def get_order(order_id: int, db: Session = Depends(get_db)) -> OrderResponse:
    row = db.query(Order).filter(Order.id == order_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "ORDER_NOT_FOUND", "message": "order not found"})
    return OrderResponse.model_validate(row)


@router.patch(
    "/{order_id}",
    response_model=OrderResponse,
    responses={
        **ORDER_COMMON_ERROR_RESPONSES,
        404: {"model": ApiErrorResponse, "description": "Not Found"},
    },
)
def update_order(order_id: int, payload: OrderUpdateRequest, db: Session = Depends(get_db)) -> OrderResponse:
    row = db.query(Order).filter(Order.id == order_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "ORDER_NOT_FOUND", "message": "order not found"})

    if payload.customer_id is not None:
        customer = db.query(Customer).filter(Customer.id == payload.customer_id).first()
        if customer is None:
            raise HTTPException(status_code=404, detail={"code": "CUSTOMER_NOT_FOUND", "message": "customer not found"})
        row.customer_id = payload.customer_id

    if payload.delivery_date is not None:
        row.delivery_date = payload.delivery_date

    if payload.note is not None or "note" in payload.model_fields_set:
        row.note = payload.note

    row.updated_by = "system_api"
    db.flush()
    write_audit_log(db, entity_type="order", entity_id=row.id, action=AuditAction.UPDATE)
    db.commit()
    db.refresh(row)
    return OrderResponse.model_validate(row)


_TRANSITION_RULES: dict[tuple[OrderStatus, OrderStatus], tuple[LineStatus, LineStatus]] = {
    (OrderStatus.confirmed, OrderStatus.allocated): (LineStatus.open, LineStatus.allocated),
    (OrderStatus.allocated, OrderStatus.purchased): (LineStatus.allocated, LineStatus.purchased),
    (OrderStatus.purchased, OrderStatus.shipped): (LineStatus.purchased, LineStatus.shipped),
    (OrderStatus.shipped, OrderStatus.invoiced): (LineStatus.shipped, LineStatus.invoiced),
}


@router.post(
    "/{order_id}/bulk-transition",
    response_model=OrderBulkTransitionResponse,
    responses={
        **ORDER_COMMON_ERROR_RESPONSES,
        404: {"model": ApiErrorResponse, "description": "Not Found"},
        409: {"model": ApiErrorResponse, "description": "Conflict"},
    },
)
def bulk_transition_order(order_id: int, payload: OrderBulkTransitionRequest, db: Session = Depends(get_db)) -> OrderBulkTransitionResponse:
    order = db.query(Order).filter(Order.id == order_id).first()
    if order is None:
        raise HTTPException(status_code=404, detail={"code": "ORDER_NOT_FOUND", "message": "order not found"})

    if payload.from_status == payload.to_status:
        raise HTTPException(status_code=422, detail={"code": "INVALID_TRANSITION_PAIR", "message": "from_status and to_status must differ"})

    key = (payload.from_status, payload.to_status)
    if key not in _TRANSITION_RULES:
        raise HTTPException(status_code=422, detail={"code": "INVALID_TRANSITION_PAIR", "message": "invalid transition pair"})

    if order.status != payload.from_status:
        raise HTTPException(status_code=409, detail={"code": "ORDER_STATUS_MISMATCH", "message": "order status mismatch"})

    from_line, to_line = _TRANSITION_RULES[key]
    lines = db.query(OrderItem).filter(OrderItem.order_id == order_id, OrderItem.line_status == from_line).all()
    if not lines:
        raise HTTPException(status_code=409, detail={"code": "STATUS_NO_TARGET_LINES", "message": "no eligible lines"})

    for line in lines:
        line.line_status = to_line

    order.status = payload.to_status
    order.updated_by = "system_api"
    db.flush()
    write_audit_log(db, entity_type="order", entity_id=order.id, action=AuditAction.BULK_TRANSITION)
    db.commit()

    return OrderBulkTransitionResponse(order_id=order.id, updated_lines=len(lines), updated_order_status=order.status)


@router.post(
    "",
    response_model=OrderResponse,
    status_code=201,
    responses={
        **ORDER_COMMON_ERROR_RESPONSES,
        404: {"model": ApiErrorResponse, "description": "Not Found"},
        409: {"model": ApiErrorResponse, "description": "Conflict"},
    },
)
def create_order(payload: OrderCreateRequest, db: Session = Depends(get_db)) -> OrderResponse:
    customer = db.query(Customer).filter(Customer.id == payload.customer_id).first()
    if customer is None:
        raise HTTPException(status_code=404, detail={"code": "CUSTOMER_NOT_FOUND", "message": "customer not found"})

    row = None
    for _ in range(5):
        generated_order_no = f"ORD-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6].upper()}"
        if db.query(Order).filter(Order.order_no == generated_order_no).first() is not None:
            continue

        row = Order(
            order_no=generated_order_no,
            customer_id=payload.customer_id,
            order_datetime=datetime.now(UTC),
            delivery_date=payload.delivery_date,
            status=OrderStatus.new,
            note=payload.note,
            created_by="system_api",
            updated_by="system_api",
        )
        db.add(row)
        db.flush()
        break

    if row is None:
        raise HTTPException(status_code=409, detail={"code": "ORDER_NO_GENERATION_FAILED", "message": "failed to generate order_no"})

    write_audit_log(db, entity_type="order", entity_id=row.id, action=AuditAction.CREATE)
    db.commit()
    db.refresh(row)
    return OrderResponse.model_validate(row)


def _validate_order_item_pricing(payload: OrderItemCreateRequest | OrderItemUpdateRequest) -> None:
    pricing_basis = payload.pricing_basis
    if pricing_basis == PricingBasis.uom_count:
        if payload.unit_price_uom_count is None:
            raise HTTPException(status_code=422, detail={"code": "VALIDATION_FAILED", "message": "unit_price_uom_count is required"})
    if pricing_basis == PricingBasis.uom_kg:
        if payload.unit_price_uom_kg is None:
            raise HTTPException(status_code=422, detail={"code": "VALIDATION_FAILED", "message": "unit_price_uom_kg is required"})


@router.get("/{order_id}/items", response_model=list[OrderItemResponse])
def list_order_items(order_id: int, db: Session = Depends(get_db)) -> list[OrderItemResponse]:
    order = db.query(Order).filter(Order.id == order_id).first()
    if order is None:
        raise HTTPException(status_code=404, detail={"code": "ORDER_NOT_FOUND", "message": "order not found"})

    rows = db.query(OrderItem).filter(OrderItem.order_id == order_id).order_by(OrderItem.id.asc()).all()
    return [OrderItemResponse.model_validate(r) for r in rows]


@router.post("/{order_id}/items", response_model=OrderItemResponse, status_code=201)
def create_order_item(order_id: int, payload: OrderItemCreateRequest, db: Session = Depends(get_db)) -> OrderItemResponse:
    order = db.query(Order).filter(Order.id == order_id).first()
    if order is None:
        raise HTTPException(status_code=404, detail={"code": "ORDER_NOT_FOUND", "message": "order not found"})

    product = db.query(Product).filter(Product.id == payload.product_id).first()
    if product is None:
        raise HTTPException(status_code=404, detail={"code": "PRODUCT_NOT_FOUND", "message": "product not found"})

    _validate_order_item_pricing(payload)

    row = OrderItem(
        order_id=order_id,
        product_id=payload.product_id,
        ordered_qty=payload.ordered_qty,
        order_uom_type=payload.order_uom_type,
        estimated_weight_kg=payload.estimated_weight_kg,
        target_price=payload.target_price,
        price_ceiling=payload.price_ceiling,
        stockout_policy=payload.stockout_policy,
        pricing_basis=payload.pricing_basis,
        unit_price_uom_count=payload.unit_price_uom_count,
        unit_price_uom_kg=payload.unit_price_uom_kg,
        note=payload.note,
        comment=payload.comment,
    )
    db.add(row)
    db.flush()
    order.updated_by = "system_api"
    db.commit()
    db.refresh(row)
    return OrderItemResponse.model_validate(row)


@router.post("/{order_id}/items/bulk", response_model=OrderItemsBulkCreateResponse)
def bulk_create_order_items(order_id: int, payload: OrderItemsBulkCreateRequest, db: Session = Depends(get_db)) -> OrderItemsBulkCreateResponse:
    order = db.query(Order).filter(Order.id == order_id).first()
    if order is None:
        raise HTTPException(status_code=404, detail={"code": "ORDER_NOT_FOUND", "message": "order not found"})

    success = 0
    errors: list[dict] = []
    for idx, item in enumerate(payload.items):
        product = db.query(Product).filter(Product.id == item.product_id).first()
        if product is None:
            errors.append({"index": idx, "field": "product_id", "code": "PRODUCT_NOT_FOUND", "message": "product not found"})
            continue
        try:
            _validate_order_item_pricing(item)
        except HTTPException as e:
            errors.append({"index": idx, "field": "pricing_basis", "code": e.detail.get("code", "VALIDATION_FAILED"), "message": e.detail.get("message", "validation failed")})
            continue

        db.add(
            OrderItem(
                order_id=order_id,
                product_id=item.product_id,
                ordered_qty=item.ordered_qty,
                order_uom_type=item.order_uom_type,
                estimated_weight_kg=item.estimated_weight_kg,
                target_price=item.target_price,
                price_ceiling=item.price_ceiling,
                stockout_policy=item.stockout_policy,
                pricing_basis=item.pricing_basis,
                unit_price_uom_count=item.unit_price_uom_count,
                unit_price_uom_kg=item.unit_price_uom_kg,
                note=item.note,
                comment=item.comment,
            )
        )
        success += 1

    order.updated_by = "system_api"
    db.commit()
    return OrderItemsBulkCreateResponse(total=len(payload.items), success=success, failed=len(payload.items) - success, errors=errors)


@router.patch("/{order_id}/items/{item_id}", response_model=OrderItemResponse)
def update_order_item(order_id: int, item_id: int, payload: OrderItemUpdateRequest, db: Session = Depends(get_db)) -> OrderItemResponse:
    order = db.query(Order).filter(Order.id == order_id).first()
    if order is None:
        raise HTTPException(status_code=404, detail={"code": "ORDER_NOT_FOUND", "message": "order not found"})

    row = db.query(OrderItem).filter(OrderItem.id == item_id, OrderItem.order_id == order_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "RESOURCE_NOT_FOUND", "message": "order item not found"})

    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(row, k, v)

    if payload.pricing_basis is not None or payload.unit_price_uom_count is not None or payload.unit_price_uom_kg is not None:
        pb = payload.pricing_basis or row.pricing_basis
        temp = OrderItemUpdateRequest(pricing_basis=pb, unit_price_uom_count=row.unit_price_uom_count, unit_price_uom_kg=row.unit_price_uom_kg)
        _validate_order_item_pricing(temp)

    order.updated_by = "system_api"
    db.commit()
    db.refresh(row)
    return OrderItemResponse.model_validate(row)


@router.delete("/{order_id}/items/{item_id}", status_code=204)
def delete_order_item(order_id: int, item_id: int, db: Session = Depends(get_db)) -> None:
    order = db.query(Order).filter(Order.id == order_id).first()
    if order is None:
        raise HTTPException(status_code=404, detail={"code": "ORDER_NOT_FOUND", "message": "order not found"})

    row = db.query(OrderItem).filter(OrderItem.id == item_id, OrderItem.order_id == order_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "RESOURCE_NOT_FOUND", "message": "order item not found"})

    db.delete(row)
    order.updated_by = "system_api"
    db.commit()
    return None
