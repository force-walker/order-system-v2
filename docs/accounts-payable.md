# Accounts Payable / Supplier Bill

Purchase Result is the source for unbilled purchases. A Supplier Bill Draft snapshots its Supplier payment terms, quantity, UOM, effective purchase unit cost (`final_unit_cost`, otherwise `unit_cost`), SKU, and product description. The internal permanent number is `APB-00000001` format; Supplier invoice numbers must be unique among non-cancelled Bills for the same Supplier.

Draft creation accepts one or more unclaimed Purchase Results from the same Supplier and currency. Detail quantity and unit cost may be corrected on the Draft without changing Purchase Result or customer Invoice snapshots. Subtotal is the sum of line amounts; total is `subtotal + tax + adjustment`. Bill Date is the payment-terms base date. Due Date and payment terms are frozen after finalization.

Finalized Bills accept positive payments up to the outstanding amount. Payments are voided, never hard-deleted. Payment status and overdue are derived from active payments, total, due date, status, and the Asia/Hong_Kong business date. A Bill with active payments cannot be cancelled. Cancelling an unpaid Bill releases its Purchase Results back to the unbilled candidate list.

PostgreSQL serializes claims with transaction-scoped advisory locks and trigger checks so a Purchase Result cannot be claimed by two active Bills. Supplier Invoice No checks use the same approach. These controls complement application row locks and are not Frontend-only validation.
