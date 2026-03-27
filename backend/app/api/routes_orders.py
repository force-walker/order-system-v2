from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.audit import AuditAction, write_audit_log
from app.db.session import get_db
from app.models.entities import Customer, LineStatus, Order, OrderItem, OrderStatus
from app.schemas.common import ApiErrorResponse
from app.schemas.order import OrderBulkTransitionRequest, OrderBulkTransitionResponse, OrderCreateRequest, OrderResponse

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

    exists = db.query(Order).filter(Order.order_no == payload.order_no).first()
    if exists is not None:
        raise HTTPException(status_code=409, detail={"code": "ORDER_NO_ALREADY_EXISTS", "message": "order_no already exists"})

    row = Order(
        order_no=payload.order_no,
        customer_id=payload.customer_id,
        order_datetime=datetime.now(UTC),
        delivery_date=payload.delivery_date,
        status=OrderStatus.new,
        note=payload.note,
    )
    db.add(row)
    db.flush()
    write_audit_log(db, entity_type="order", entity_id=row.id, action=AuditAction.CREATE)
    db.commit()
    db.refresh(row)
    return OrderResponse.model_validate(row)
