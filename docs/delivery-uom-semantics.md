# Delivery UOM semantics

Delivery records what the customer receives on the customer order quantity axis. It is independent from the Supplier purchase axis and the Customer invoice axis.

For every Delivery Item:

- `delivered_qty = OrderItem.ordered_qty`
- `delivered_uom = Product.order_uom`

This rule also applies to catch-weight products. For example, an Order for `2 CTN` with Purchase Results totaling `21.73 KG` produces a Delivery Item of `2 CTN` and an Invoice Item of `21.73 KG`.

`PurchaseResult.actual_weight_kg` remains the only authoritative measured-weight field. Delivery does not copy measured weight into its tables. The current Delivery API and PDF expose only delivered quantity and UOM. If a future Delivery PDF must show measured weight, it should derive the sum from the selected Purchase Results and display it separately; it must not replace `delivered_qty` or introduce another authoritative weight value.

The current cardinality remains unchanged:

- one Order has at most one Delivery (`deliveries.order_id` is unique)
- one Order Item has at most one Delivery Item (`delivery_items.order_item_id` is unique)

Rebuilding or refreshing a Delivery updates the existing Delivery and Delivery Items instead of creating duplicates.
