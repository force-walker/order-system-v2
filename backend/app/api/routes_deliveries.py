from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import Delivery, DeliveryItem, Order
from app.schemas.common import ApiErrorResponse
from app.schemas.delivery import DeliveryItemResponse, DeliveryResponse

router = APIRouter(prefix="/api/v1/deliveries", tags=["deliveries"])


def _get_delivery_or_404(db: Session, delivery_id: str) -> Delivery:
    row = db.query(Delivery).filter(Delivery.id == delivery_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "DELIVERY_NOT_FOUND", "message": "delivery not found"})
    return row


def _get_order_or_404(db: Session, order_id: str | int) -> Order:
    ident = str(order_id)
    row = db.query(Order).filter(Order.id == ident).first()
    if row is None and ident.isdigit():
        row = db.query(Order).filter(Order.legacy_id == int(ident)).first()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "ORDER_NOT_FOUND", "message": "order not found"})
    return row


@router.get("", response_model=list[DeliveryResponse])
def list_deliveries(
    order_id: str | None = Query(default=None),
    order_uuid: str | None = Query(default=None),
    shipped_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[DeliveryResponse]:
    query = db.query(Delivery)
    if order_id is not None:
        order = _get_order_or_404(db, order_id)
        query = query.filter(Delivery.order_id == order.id)
    if order_uuid is not None:
        order = _get_order_or_404(db, order_uuid)
        query = query.filter(Delivery.order_id == order.id)
    if shipped_date is not None:
        query = query.filter(Delivery.shipped_date == shipped_date)
    rows = query.order_by(Delivery.created_at.desc()).all()
    return [DeliveryResponse.model_validate(row) for row in rows]


@router.get(
    "/{delivery_id}",
    response_model=DeliveryResponse,
    responses={404: {"model": ApiErrorResponse, "description": "Not Found"}},
)
def get_delivery(delivery_id: str, db: Session = Depends(get_db)) -> DeliveryResponse:
    return DeliveryResponse.model_validate(_get_delivery_or_404(db, delivery_id))


@router.get(
    "/uuid/{delivery_uuid}",
    response_model=DeliveryResponse,
    responses={404: {"model": ApiErrorResponse, "description": "Not Found"}},
)
def get_delivery_by_uuid(delivery_uuid: str, db: Session = Depends(get_db)) -> DeliveryResponse:
    return DeliveryResponse.model_validate(_get_delivery_or_404(db, delivery_uuid))


@router.get(
    "/{delivery_id}/items",
    response_model=list[DeliveryItemResponse],
    responses={404: {"model": ApiErrorResponse, "description": "Not Found"}},
)
def list_delivery_items(delivery_id: str, db: Session = Depends(get_db)) -> list[DeliveryItemResponse]:
    delivery = _get_delivery_or_404(db, delivery_id)
    rows = db.query(DeliveryItem).filter(DeliveryItem.delivery_id == delivery.id).order_by(DeliveryItem.created_at.asc()).all()
    return [DeliveryItemResponse.model_validate(row) for row in rows]


@router.get(
    "/uuid/{delivery_uuid}/items",
    response_model=list[DeliveryItemResponse],
    responses={404: {"model": ApiErrorResponse, "description": "Not Found"}},
)
def list_delivery_items_by_uuid(delivery_uuid: str, db: Session = Depends(get_db)) -> list[DeliveryItemResponse]:
    delivery = _get_delivery_or_404(db, delivery_uuid)
    rows = db.query(DeliveryItem).filter(DeliveryItem.delivery_id == delivery.id).order_by(DeliveryItem.created_at.asc()).all()
    return [DeliveryItemResponse.model_validate(row) for row in rows]
