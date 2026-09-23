from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.audit import AuditAction, write_audit_log
from app.models.entities import LineStatus, Order, OrderItem, OrderStatus, Product, SupplierAllocation


@dataclass(frozen=True)
class AllocationIncompleteReason:
    order_item_id: str | None
    code: str
    message: str


@dataclass(frozen=True)
class AllocationCompletionResult:
    complete: bool
    complete_item_ids: frozenset[str]
    reasons: tuple[AllocationIncompleteReason, ...]


def _normalized_uom(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    return normalized or None


def _positive_quantity(value) -> Decimal | None:
    if value is None:
        return None
    quantity = Decimal(str(value))
    return quantity if quantity > 0 else None


def evaluate_order_allocation_completion(db: Session, order_id: str) -> AllocationCompletionResult:
    rows = (
        db.query(OrderItem, Product)
        .join(Product, Product.id == OrderItem.product_id)
        .filter(OrderItem.order_id == order_id)
        .order_by(OrderItem.line_no.asc(), OrderItem.id.asc())
        .all()
    )
    active_rows = [(item, product) for item, product in rows if item.line_status != LineStatus.cancelled]
    if not active_rows:
        return AllocationCompletionResult(
            complete=False,
            complete_item_ids=frozenset(),
            reasons=(AllocationIncompleteReason(None, "NO_ACTIVE_ORDER_ITEMS", "order has no non-cancelled items"),),
        )

    item_ids = [item.id for item, _ in active_rows]
    allocations = (
        db.query(SupplierAllocation)
        .filter(SupplierAllocation.order_item_id.in_(item_ids))
        .order_by(SupplierAllocation.id.asc())
        .all()
    )
    by_item: dict[str, list[SupplierAllocation]] = {item_id: [] for item_id in item_ids}
    for allocation in allocations:
        by_item.setdefault(allocation.order_item_id, []).append(allocation)

    reasons: list[AllocationIncompleteReason] = []
    complete_item_ids: set[str] = set()

    for item, product in active_rows:
        item_reasons: list[AllocationIncompleteReason] = []
        order_uom = _normalized_uom(product.order_uom)
        purchase_uom = _normalized_uom(product.purchase_uom)
        if order_uom != purchase_uom:
            item_reasons.append(
                AllocationIncompleteReason(
                    item.id,
                    "UOM_MISMATCH_REQUIRES_MASTER_CORRECTION",
                    (
                        "order UOM and purchase UOM must match until an explicit "
                        f"conversion workflow exists ({product.order_uom} != {product.purchase_uom})"
                    ),
                )
            )
        item_allocations = by_item.get(item.id, [])
        parents = [allocation for allocation in item_allocations if not allocation.is_split_child]
        parent = parents[-1] if parents else None
        if parent is None:
            item_reasons.append(AllocationIncompleteReason(item.id, "ALLOCATION_MISSING", "allocation is missing"))
        else:
            expected_quantity = Decimal(str(item.ordered_qty))
            expected_uom = purchase_uom
            split_children = [
                allocation
                for allocation in item_allocations
                if allocation.is_split_child
                and allocation.parent_allocation_id == parent.id
                and parent.split_group_id is not None
                and allocation.split_group_id == parent.split_group_id
            ]

            targets = split_children if parent.split_group_id is not None else [parent]
            if parent.split_group_id is not None and len(split_children) < 2:
                item_reasons.append(
                    AllocationIncompleteReason(item.id, "SPLIT_PARTS_INCOMPLETE", "split allocation requires at least two current child rows")
                )

            total_quantity = Decimal("0")
            for allocation in targets:
                if allocation.final_supplier_id is None:
                    item_reasons.append(AllocationIncompleteReason(item.id, "SUPPLIER_MISSING", "final supplier is missing"))
                quantity = _positive_quantity(allocation.final_qty)
                if quantity is None:
                    item_reasons.append(AllocationIncompleteReason(item.id, "FINAL_QTY_INVALID", "final quantity must be greater than zero"))
                else:
                    total_quantity += quantity
                actual_uom = _normalized_uom(allocation.final_uom)
                if actual_uom is None:
                    item_reasons.append(AllocationIncompleteReason(item.id, "FINAL_UOM_MISSING", "final UOM is missing"))
                elif actual_uom != expected_uom:
                    item_reasons.append(
                        AllocationIncompleteReason(
                            item.id,
                            "FINAL_UOM_MISMATCH",
                            f"final UOM must match product purchase UOM ({product.purchase_uom})",
                        )
                    )

            if total_quantity != expected_quantity:
                item_reasons.append(
                    AllocationIncompleteReason(
                        item.id,
                        "FINAL_QTY_MISMATCH",
                        f"final allocation quantity {total_quantity} must equal ordered quantity {expected_quantity}",
                    )
                )

        if item_reasons:
            reasons.extend(item_reasons)
        else:
            complete_item_ids.add(item.id)

    return AllocationCompletionResult(
        complete=not reasons and len(complete_item_ids) == len(active_rows),
        complete_item_ids=frozenset(complete_item_ids),
        reasons=tuple(reasons),
    )


def synchronize_confirmed_order_allocation_status(
    db: Session,
    order: Order,
    *,
    reason_code: str = "allocation_completion",
) -> AllocationCompletionResult:
    result = evaluate_order_allocation_completion(db, order.id)
    if order.status != OrderStatus.confirmed:
        return result

    active_items = (
        db.query(OrderItem)
        .filter(OrderItem.order_id == order.id, OrderItem.line_status != LineStatus.cancelled)
        .order_by(OrderItem.line_no.asc(), OrderItem.id.asc())
        .all()
    )
    for item in active_items:
        if item.line_status not in {LineStatus.open, LineStatus.allocated}:
            continue
        target_status = LineStatus.allocated if item.id in result.complete_item_ids else LineStatus.open
        if item.line_status == target_status:
            continue
        before = {"line_status": item.line_status.value, "shipped_date": str(item.shipped_date) if item.shipped_date else None}
        item.line_status = target_status
        item.shipped_date = order.delivery_date if target_status == LineStatus.allocated else None
        write_audit_log(
            db,
            entity_type="order_item",
            entity_id=item.id,
            action=AuditAction.UPDATE,
            reason_code=reason_code,
            before=before,
            after={"line_status": item.line_status.value, "shipped_date": str(item.shipped_date) if item.shipped_date else None},
        )

    if result.complete:
        before = {"order_status": order.status.value}
        order.status = OrderStatus.allocated
        order.updated_by = "system_api"
        write_audit_log(
            db,
            entity_type="order",
            entity_id=order.id,
            action=AuditAction.BULK_TRANSITION,
            reason_code=reason_code,
            before=before,
            after={"order_status": order.status.value},
        )
    return result
