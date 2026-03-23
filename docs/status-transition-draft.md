# Status Transition Draft (Order Lifecycle)

Updated: 2026-03-15

## Final status policy (MVP)

Main flow:

`new → confirmed → allocated → purchased → shipped → invoiced`

Exception flow:

`* → cancelled` (allowed with role/condition controls)

### Notes
- `invoiced` is the terminal status for MVP completion.
- `completed` is removed.
- `paid` is intentionally deferred to a future version (accounting scope).

---

## Transition rules

## Global evaluation policy (MVP)
- Line status is updated first.
- Order-level status transition is executed only by explicit user-triggered bulk action.
- `confirmed -> allocated`, `allocated -> purchased`, `shipped -> invoiced` are line-driven transitions.
- `purchased -> shipped` is evaluated in one batch (order-level execution).
- Automatic order-status promotion from line aggregation is not applied in MVP.
- Multiple user-triggered transition executions on the same business day are allowed.
- If zero target lines are eligible/updated, return conflict (`STATUS_NO_TARGET_LINES`).

## 1) `new → confirmed`
- Actor: Order Entry, Admin
- Required:
  - customer + delivery date
  - at least 1 valid order line
  - mandatory pricing basis fields

## 2) `confirmed → allocated` (line-driven)
- Actor: Buyer, Admin
- Required (per target line):
  - allocation run completed for target lines
  - target line is `line_status=open`
  - `final_supplier_id` exists and `final_qty > 0`
- Behavior:
  - only eligible lines move to `allocated`
  - order status transition is applied only when user explicitly runs order-level bulk transition

## 3) `allocated → purchased` (line-driven)
- Actor: Buyer, Admin
- Required (per target line):
  - purchase result exists for the line/allocation
  - required fields entered (`supplier_id`, `purchased_qty`, `final_unit_cost`, `result_status`)
  - `result_status != not_filled`
- Behavior:
  - only eligible lines move to `purchased`
  - order status transition is applied only when user explicitly runs order-level bulk transition

## 4) `purchased → shipped` (order batch)
- Actor: Buyer, Admin
- Required:
  - all active non-cancelled lines are shippable
  - no active line remains `result_status=not_filled`
  - shortage handling fixed when `shortage_qty > 0`
- Behavior:
  - single batch decision for the order
  - lines that cannot be shipped must be explicitly set to `cancelled` by user before retry

## 5) `shipped → invoiced` (line-driven + invoice finalize)
- Actor: Billing, Admin
- Required (for selected invoice lines):
  - invoice generated and finalized (split invoicing allowed)
  - catch-weight lines have `actual_weight_kg`
  - price/tax validations pass
- Behavior:
  - selected eligible lines move to `invoiced`
  - non-selected / unfinished lines are not auto-cancelled
  - bulk cancel is allowed only by explicit user input

---

## Cancel rules (`* → cancelled`)

- Allowed from: `new`, `confirmed`, `allocated`, `purchased`, `shipped`
- Not allowed from: `invoiced` (MVP default hard-stop)
- Bulk cancel policy:
  - no automatic bulk cancel before invoicing
  - bulk cancel is executed only by explicit user input (manual operation)
- Required on cancel:
  - cancel reason code
  - actor + timestamp
  - audit log (`before/after`, reason)
- Cancel execution rule:
  - related `line_status` and `invoice_line_status` are updated together

Suggested cancel reason codes:
- `customer_cancelled`
- `stockout_unresolved`
- `data_error`
- `duplicate_order`
- `policy_exception`

---

## Line status policy (`order_items.line_status`)

Line-level processing status is managed separately from order header status.
Until a line is explicitly cancelled, it remains attached to the original order.

Allowed values (MVP):
- `open`
- `allocated`
- `purchased`
- `shipped`
- `invoiced`
- `cancelled`

Recommended progression:
`open -> allocated -> purchased -> shipped -> invoiced` (+ `cancelled` by policy)

## Cutoff / edit policy

- cutoff前: 通常権限で編集可
- cutoff後: order creator / Admin のみ編集可
- cutoff後に変更する場合は `change_reason` 必須
- cutoff後に明細変更した場合、`procurement_list_regeneration` の実行要否を記録

## Audit requirements

Every state change must store:
- who changed status
- when
- from_status / to_status
- reason_code (required for cancel, reopen-like operations)
- optional note

---

## Future extension (vNext)

When accounting is in scope, add:
- `paid` status
- `invoiced → paid` transition conditions
- payment reconciliation + lock policy
