from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.audit import AuditAction, write_audit_log
from app.models.entities import LineStatus, Order, OrderItem, OrderStatus, PricingBasis, Product, PurchaseResult, SupplierAllocation


@dataclass(frozen=True)
class PurchaseCompletionResult:
    complete: bool
    complete_item_ids: frozenset[str]


def _normalized_uom(value: str | None) -> str | None:
    normalized = (value or "").strip().casefold()
    return normalized or None


def evaluate_order_purchase_completion(db: Session, order_id: str) -> PurchaseCompletionResult:
    """Evaluate whether every current allocation has been fully received.

    A split parent is represented by its current split children. A normal parent
    represents itself. Historical allocations and obsolete split children are not
    completion targets.
    """
    items = (
        db.query(OrderItem)
        .filter(OrderItem.order_id == order_id)
        .order_by(OrderItem.line_no.asc(), OrderItem.id.asc())
        .all()
    )
    active_items = [item for item in items if item.line_status != LineStatus.cancelled]
    if not active_items:
        return PurchaseCompletionResult(False, frozenset())

    complete_item_ids: set[str] = set()
    for item in active_items:
        product = db.query(Product).filter(Product.id == item.product_id).first()
        if product is None:
            continue
        requires_weight = product.is_catch_weight or product.weight_capture_required or item.pricing_basis == PricingBasis.uom_kg
        allocations = (
            db.query(SupplierAllocation)
            .filter(SupplierAllocation.order_item_id == item.id)
            .order_by(SupplierAllocation.id.asc())
            .all()
        )
        parents = [allocation for allocation in allocations if not allocation.is_split_child]
        parent = parents[-1] if parents else None
        if parent is None:
            continue

        if parent.split_group_id is not None:
            targets = [
                allocation
                for allocation in allocations
                if allocation.is_split_child
                and allocation.parent_allocation_id == parent.id
                and allocation.split_group_id == parent.split_group_id
            ]
            if len(targets) < 2:
                continue
        else:
            targets = [parent]

        item_complete = True
        for allocation in targets:
            if allocation.final_supplier_id is None or allocation.final_qty is None or Decimal(str(allocation.final_qty)) <= 0:
                item_complete = False
                break
            results = db.query(PurchaseResult).filter(PurchaseResult.allocation_id == allocation.id).all()
            if not results:
                item_complete = False
                break
            if any(not result.invoiceable_flag for result in results):
                item_complete = False
                break
            if requires_weight and any(result.actual_weight_kg is None for result in results):
                item_complete = False
                break
            expected_uom = _normalized_uom(allocation.final_uom)
            if expected_uom is None or any(_normalized_uom(result.purchased_uom) != expected_uom for result in results):
                item_complete = False
                break
            received = sum((Decimal(str(result.purchased_qty)) for result in results), Decimal("0"))
            if received != Decimal(str(allocation.final_qty)):
                item_complete = False
                break

        if item_complete:
            complete_item_ids.add(item.id)

    return PurchaseCompletionResult(
        complete=len(complete_item_ids) == len(active_items),
        complete_item_ids=frozenset(complete_item_ids),
    )


def synchronize_order_purchase_status(
    db: Session,
    order: Order,
    *,
    actor: str | None = None,
    reason_code: str = "purchase_result_completion",
) -> PurchaseCompletionResult:
    result = evaluate_order_purchase_completion(db, order.id)
    if order.status not in {OrderStatus.allocated, OrderStatus.purchased}:
        return result

    audit_actor = actor or "system_api"
    active_items = (
        db.query(OrderItem)
        .filter(OrderItem.order_id == order.id, OrderItem.line_status != LineStatus.cancelled)
        .order_by(OrderItem.line_no.asc(), OrderItem.id.asc())
        .all()
    )
    for item in active_items:
        if item.line_status not in {LineStatus.allocated, LineStatus.purchased}:
            continue
        target = LineStatus.purchased if item.id in result.complete_item_ids else LineStatus.allocated
        if item.line_status == target:
            continue
        before = {"line_status": item.line_status.value}
        item.line_status = target
        write_audit_log(
            db,
            entity_type="order_item",
            entity_id=item.id,
            action=AuditAction.UPDATE,
            actor=audit_actor,
            reason_code=reason_code,
            before=before,
            after={"line_status": item.line_status.value, "order_id": order.id},
        )

    target_order_status = OrderStatus.purchased if result.complete else OrderStatus.allocated
    if order.status != target_order_status:
        before = {"order_status": order.status.value}
        order.status = target_order_status
        order.updated_by = audit_actor
        write_audit_log(
            db,
            entity_type="order",
            entity_id=order.id,
            action=AuditAction.BULK_TRANSITION,
            actor=audit_actor,
            reason_code=reason_code,
            before=before,
            after={"order_status": order.status.value},
        )
    return result
