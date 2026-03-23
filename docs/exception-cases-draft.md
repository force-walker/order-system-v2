# Exception Cases Draft (MVP)

Updated: 2026-03-15

## Goal
Define operational exception patterns so users can act consistently and system behavior is deterministic.

---

## Exception Case List

## E1. Partial fulfillment
- Situation: Supplier can fulfill only part of requested qty.
- Inputs:
  - available qty
  - remaining qty (`shortage_qty`)
  - customer priority
- Required action:
  - record `result_status=partially_filled`
  - set shortage policy (`backorder` / `cancel` / `substitute` / `split`)
  - set `shortage_reason_code`
  - if reason is `manual_adjustment`, `shortage_note` is mandatory
  - notify customer-facing note
- Audit: mandatory

## E2. Supplier stockout
- Situation: Assigned supplier cannot provide item.
- Inputs:
  - stockout confirmation
  - alternative suppliers / lead times
- Required action:
  - manual override or split-line
  - reason code `stockout`
- Audit: mandatory

## E3. Substitute item
- Situation: Original item unavailable, substitute proposed.
- Inputs:
  - substitute sku/spec
  - price delta
  - customer approval flag
- Required action:
  - mark `result_status=substituted`
  - preserve original line reference
  - create substitute line mapping (`original_line_id -> substitute_line_id`)
- Audit: mandatory

## E4. Catch-weight missing actual weight
- Situation: `uom_kg` line has no `actual_weight_kg` at invoice timing.
- Required action:
  - block invoice finalization
  - route back to purchase result registration
- Audit: automatic block event log

## E5. Post-allocation price change
- Situation: final purchase unit cost differs from assumed value.
- Inputs:
  - final_unit_cost
  - effective timestamp
- Required action:
  - update purchase result with `final_unit_cost`
  - keep previous value in audit
- Audit: mandatory

## E6. Customer-requested urgent change
- Situation: customer changes qty/date after confirmed.
- Inputs:
  - requested delta
  - current allocation/purchase state
- Required action:
  - allow only by role + reason
  - re-run validation gate
- Audit: mandatory

## E7. Cancellation after shipping
- Situation: cancel request when shipment already started.
- Required action:
  - admin-only
  - mandatory reason and impact note
  - financial handling handoff (outside MVP)
- Audit: mandatory

## E8. Duplicate order detected
- Situation: same customer/date/items duplicated by mistake.
- Required action:
  - cancel duplicate line/order with reason `duplicate_order`
  - preserve original active order
- Audit: mandatory

---

## Cross-case mandatory fields
- `reason_code`
- `operator`
- `operation_time`
- `before_json` / `after_json`
- `note` (optional but recommended)

---

## Shipped transition gate (shortage-aware)
Transition `purchased -> shipped` is blocked unless all active lines satisfy:
- `result_status != not_filled`
- Required fields entered (`supplier_id`, `purchased_qty`, `final_unit_cost`, `result_status`)
- If `shortage_qty > 0`, shortage policy and reason are fixed
- if `invoiceable_flag=false`, block reason is explicitly recorded

## Hard-stop behavior policy
When a hard-stop occurs, the attempted operation fails atomically and no business status is changed:
- order/invoice/line status remains unchanged
- transaction is rolled back (all-or-nothing)
- blocked attempt is audit-logged with reason code
- record remains editable; user can fix and retry (no operational lock)

## Open decisions for next refinement
- Which exception cases require supervisor approval?
- SLA for unresolved backorder cases
- Customer notification ownership (Order Entry vs Buyer)
