from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import Customer, Order, OrderStatus
from app.schemas.order import OrderCreateRequest, OrderResponse

router = APIRouter(prefix="/api/v1/orders", tags=["orders"])


@router.get("", response_model=list[OrderResponse])
def list_orders(db: Session = Depends(get_db)) -> list[OrderResponse]:
    rows = db.query(Order).order_by(Order.id.desc()).all()
    return [OrderResponse.model_validate(r) for r in rows]


@router.get("/{order_id}", response_model=OrderResponse)
def get_order(order_id: int, db: Session = Depends(get_db)) -> OrderResponse:
    row = db.query(Order).filter(Order.id == order_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "ORDER_NOT_FOUND", "message": "order not found"})
    return OrderResponse.model_validate(row)


@router.post("", response_model=OrderResponse, status_code=201)
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
    db.commit()
    db.refresh(row)
    return OrderResponse.model_validate(row)
