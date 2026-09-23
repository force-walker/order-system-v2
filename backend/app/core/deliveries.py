from sqlalchemy.orm import Session

from app.core.numbering import ensure_delivery_header_numbers, ensure_delivery_item_number, ensure_order_delivery_number
from app.models.entities import Delivery, DeliveryItem, Order, OrderItem, Product


def _delivered_qty(order_item: OrderItem) -> float:
    """Delivery stays on the customer order quantity axis."""
    return float(order_item.ordered_qty)


def _delivered_uom(product: Product) -> str:
    """Measured weight belongs to PurchaseResult and is not copied to Delivery."""
    return product.order_uom


def ensure_delivery_document(db: Session, order: Order) -> Delivery:
    ensure_order_delivery_number(db, order)
    shipped_date = order.shipped_date or order.delivery_date

    rows = (
        db.query(OrderItem, Product)
        .join(Product, Product.id == OrderItem.product_id)
        .filter(OrderItem.order_id == order.id)
        .order_by(OrderItem.line_no.asc(), OrderItem.created_at.asc())
        .all()
    )
    if not rows:
        raise ValueError("delivery cannot be created without at least one item")

    delivery = db.query(Delivery).filter(Delivery.order_id == order.id).first()
    if delivery is None:
        delivery = Delivery(
            delivery_no="pending",
            tracking_no=order.tracking_no,
            order_id=order.id,
            customer_id=order.customer_id,
            delivery_date=order.delivery_date,
            shipped_date=shipped_date,
        )
        ensure_delivery_header_numbers(db, delivery)
        db.add(delivery)
        db.flush()
        order.delivery_no = delivery.delivery_no
        db.flush()
    else:
        ensure_delivery_header_numbers(db, delivery)
        order.delivery_no = delivery.delivery_no
        delivery.tracking_no = order.tracking_no
        delivery.customer_id = order.customer_id
        delivery.delivery_date = order.delivery_date
        delivery.shipped_date = shipped_date

    existing_items = {
        item.order_item_id: item
        for item in db.query(DeliveryItem).filter(DeliveryItem.delivery_id == delivery.id).all()
    }
    for order_item, product in rows:
        delivered_qty = _delivered_qty(order_item)
        delivered_uom = _delivered_uom(product)
        item = existing_items.get(order_item.id)
        if item is None:
            item = DeliveryItem(
                delivery_id=delivery.id,
                order_item_id=order_item.id,
                product_id=order_item.product_id,
                delivery_line_no="pending",
                delivered_qty=delivered_qty,
                delivered_uom=delivered_uom,
                shipped_date=shipped_date,
            )
            ensure_delivery_item_number(db, delivery, item)
            db.add(item)
            db.flush()
        else:
            item.product_id = order_item.product_id
            item.delivered_qty = delivered_qty
            item.delivered_uom = delivered_uom
            item.shipped_date = shipped_date

    return delivery
