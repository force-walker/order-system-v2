# Allocation Flow Draft: Auto Split + Manual Override

## Goal
Speed up purchasing with automatic supplier allocation, while guaranteeing human control for real-world constraints.

---

## Actors
- **Order Entry Staff (受注担当)**
- **Buyer/Purchasing Staff (買い付け担当)**
- **Supervisor (optional unlock/approval)**

---

## End-to-End Flow

1. **Cutoff / Batch Creation**
   - System creates a purchasing batch at cutoff time (e.g., 01:00).
   - Includes all eligible order lines in `confirmed` state.

2. **Auto Allocation Execution**
   - Engine applies mapping rules:
     - Product→Preferred supplier
     - Customer-specific supplier override (if any)
     - Time/day constraints
     - Minimum lot constraints (future)
   - Produces `suggested_supplier`, `suggested_qty`.

3. **Review Screen**
   - Three views (must share common columns/behavior):
     - By Supplier (for purchase dispatch)
     - By Customer (for order consistency)
     - By Product (for consolidation)
   - Warning badges:
     - unassigned supplier
     - quantity mismatch
     - catch-weight item with no planned handling note

4. **Manual Adjustment**
   - Buyer can:
     - Change supplier
     - Split one line into multiple suppliers
     - Adjust final qty/uom
     - Update business decision fields (target price, stockout response, comments)
   - System requires:
     - `override_reason_code`
     - optional note
   - All edits are audit-logged.

5. **Validation Gate**
   - Block confirm if:
     - unassigned lines remain
     - invalid qty (<= 0)
     - required fields missing
     - split-child totals do not match parent allocation qty
     - split-child UOM does not match parent UOM
   - Show summary totals by supplier/product/customer.

6. **Confirm & Lock Version**
   - Save as versioned allocation set (`v1 auto`, `v2 adjusted`, ...)
   - Batch status → `ready_to_purchase`
   - Generate printable/exportable supplier purchase list.

6.1 **Procurement List Regeneration (after cutoff changes)**
   - Regeneration target policy:
     - default target = newly added `open` lines
     - lines manually returned from `allocated -> open` are included
   - Major-change judgement is user-driven (not auto-detected by system).
   - Existing allocation values should be preserved as much as possible when re-generating.
   - Full rollback policy: if regeneration fails, no status/data changes are committed.

6.2 **Double-execution prevention (same order)**
   - System places an order-level regeneration lock while regeneration is running.
   - Second regeneration request for the same order returns `409 Conflict`.
   - Lock is released on success/failure completion.

7. **Purchase Result Registration**
   - Buyer records actual outcomes (`full/partial/failed/substitute`)
   - Catch-weight actuals recorded where needed
   - Final purchase unit price input is required for cost settlement (`final_unit_cost`)

---

## What "All edits are audit-logged" means
Any allocation change must be recorded in audit history so we can trace who changed what and why.

Minimum audit payload:
- `who`: user id/name
- `when`: timestamp
- `what`: before/after values
- `why`: reason code + optional note

Covered actions:
- Change supplier
- Change qty/uom
- Split line / revert split
- Revert to suggested
- Bulk set supplier
- Update target price / stockout policy / comment

---

## UI Behavior Requirements

## A) Auto Allocation Page
- Button: `Run Auto Allocation`
- Show runtime + count processed
- Show high-level success/failure summary

## B) Allocation Review Grid (Common Schema for all views)
Common columns (minimum):
- Customer
- Product
- Ordered Qty/UOM
- Suggested Supplier
- Final Supplier (editable)
- Suggested Qty
- Final Qty (editable)
- Manual Override flag
- Reason code
- **Target Price (希望価格)**
- **Stockout Policy (欠品時対応)**
- **Comment (コメント)**

Actions:
- `Change supplier`
- `Split line`
- `Revert to suggested`
- `Bulk set supplier`

## C) By Supplier Grid
Purpose:
- Dispatch and confirm purchase instructions per supplier

Additional columns:
- Supplier group total qty
- Ordered Qty（受注数量）
- Final Qty（発注数量）※発注時に使う数量
- Supplier dispatch status
- Last supplier response timestamp

## D) By Customer Grid
Purpose:
- Ensure customer-level consistency and shortage communication

Additional columns:
- Delivery date/time window
- Customer priority
- Customer-facing shortage note

## E) By Product Grid
Purpose:
- Consolidate demand and compare sourcing options

Additional columns:
- Total demand qty by product
- Supplier candidates / split ratio
- Price variance vs target price

## F) Conflict and Warning Panel
- Unassigned lines
- Split lines count
- Catch-weight lines requiring later actual weight
- Missing target price count (if policy makes it mandatory)
- Missing stockout policy count

## G) Confirm Dialog (Two-Step)
- Step 1: preview totals
- Step 2: explicit confirm with user name/password/2nd click (MVP: second click)

---

## Suggested Override Reason Codes
- `stockout`
- `better_price`
- `quality_issue`
- `urgent_delivery`
- `customer_request`
- `manual_correction`

---

## Suggested Stockout Policy Codes
- `backorder` (入荷待ち)
- `substitute` (代替品提案)
- `cancel` (キャンセル)
- `split` (分割対応)

---

## Non-Functional Safety
- Every override includes `who/when/why`.
- Version locking after confirm.
- Supervisor unlock (future option).
- Export snapshot to CSV/PDF for fallback operations.
