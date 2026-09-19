from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.entities import Order


def get_order_or_404(db: Session, order_id: str | int) -> Order:
    """Resolve the primary ID first, then a numeric legacy ID for compatibility."""
    ident = str(order_id)
    row = db.query(Order).filter(Order.id == ident).first()
    if row is None and ident.isdigit():
        row = db.query(Order).filter(Order.legacy_id == int(ident)).first()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "ORDER_NOT_FOUND", "message": "order not found"})
    return row
