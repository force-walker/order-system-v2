# Invoice Rules Draft: Mixed Piece + Catch-Weight Billing

## Goal
Support invoices that can contain both fixed-unit items and catch-weight items in the same document, with deterministic and auditable calculations.

---

## Line Calculation Rules

## Rule A: Piece-based pricing
When `pricing_basis = uom_count`

`line_subtotal = ordered_qty × unit_price_uom_count`

Then:
- `line_after_discount = line_subtotal - discount_amount`
- `line_tax` can be calculated as reference value for line display/debug
- `line_total = line_after_discount + line_tax` (reference)

Note:
- Official tax amount for finalize is invoice-level only:
  `invoice_tax_total = floor(invoice_subtotal × tax_rate)`
- If line-level reference tax and invoice-level tax differ due to rounding, invoice-level value is authoritative.

## Rule B: Catch-weight pricing
When `pricing_basis = uom_kg`

`line_subtotal = actual_weight_kg × unit_price_uom_kg`

Then same discount/tax flow as above.

## Rule C: Discount precedence
Discount is applied before tax.

## Rule D: Tax on invoice total (not by line)
Tax is calculated on invoice-level taxable total.

## Rule E: Invoice total
- `invoice_subtotal = Σ line_subtotal_after_discount`
- `invoice_tax_total = floor(invoice_subtotal × tax_rate)`
- `invoice_grand_total = invoice_subtotal + invoice_tax_total`


## Rule F: Sales unit price + gross margin fields
At invoice calculation stage, system stores:
- `sales_unit_price` (customer-facing sales unit price used for billing)
- `gross_margin_rate` (internal metric, not printed)

Gross margin formula:
`gross_margin_rate = (sales_unit_price - unit_cost_basis) / unit_cost_basis`

If one invoice line is sourced from multiple purchase results (split procurement),
`unit_cost_basis` must be weighted average cost:

`unit_cost_basis = Σ(purchased_qty_i × final_unit_cost_i) / Σ(purchased_qty_i)`

Notes:
- Weighted average is calculated in purchase UOM-consistent basis.
- `gross_margin_rate` is internal-only and excluded from customer invoice PDF.

---

## Finalization Constraints (Hard Stops)
Cannot finalize invoice if any of the following is true:

1. No selected invoiceable lines for this finalize run
2. Selected lines include `invoiceable_flag=false`
3. Selected lines include `result_status=not_filled`
4. Catch-weight line missing `actual_weight_kg`
5. Required price missing (`unit_price_uom_kg` or `unit_price_uom_count`)
6. Invalid billable qty (`billable_qty <= 0` or exceeds uninvoiced remainder)
7. Tax mismatch (`tax_amount != floor(total_amount_pretax × tax_rate)`)
8. Total mismatch (`total_amount != total_amount_pretax + tax_amount`)
9. Any negative totals
10. Optimistic lock/version conflict on selected lines

---

## Display Rules (Customer-Facing)

- `gross_margin_rate` is not displayed on customer-facing invoice/PDF.

Invoice header should display a single `delivery_date`.
Order-level invoicing is the base policy, but split invoicing is allowed (multiple invoices per order with explicit line selection).
Non-selected lines remain `invoice_line_status=uninvoiced` for later invoicing or cancellation.

## Piece-based lines
Show:
- quantity in ordered UOM
- unit price per ordered UOM
- amount

## Catch-weight lines
Show:
- ordered quantity/UOM (optional reference)
- actual weight (kg)
- unit price per kg
- amount based on actual weight

Recommended line description example:
- `Fish A (Order: 1 piece, Actual: 2.43 kg × ¥3,200/kg)`

---

## Currency Rules
- Purchase currency: `JPY`
- Sales/Invoice currency: `HKD`
- FX conversion rule (rate source + timing + rounding) must be fixed before production.

## Rounding Rules
Define globally and keep fixed:

- Weight rounding: 3 decimals (`0.001 kg`)
- Currency rounding: JPY integer (`0` decimals), HKD 2 decimals
- Tax rounding policy: invoice-level floor (`floor(invoice_subtotal × tax_rate)`)

All recalculations must happen server-side with identical rules.

Meaning:
- Client-side values are reference only; server result is authoritative.
- Same input must always return same total/tax result.
- Prevents mismatch across browser/device and improves audit reproducibility.

---

## Reset to Draft Policy
Reset-to-draft is allowed to reopen a finalized invoice for correction.

- Actor: Admin only (MVP)
- Allowed when: `invoice.status = finalized`
- Required input: `reset_reason_code` (`data_error|pricing_error|tax_error|customer_change|policy_exception`)
- `reset_note` is required when `reset_reason_code=policy_exception`

On reset execution:
- `invoice.status: finalized -> draft`
- on cancel/reset operations, related `line_status` and `invoice_line_status` are updated together
- `invoice_line_status` for affected lines is reset to `uninvoiced` (uniform policy)
- invoice items are retained (not deleted), recalculation required before re-finalize

Hard-stop (reset blocked):
- invoice not in finalized status
- required reset reason missing
- optimistic lock/version conflict

## Auditability Requirements
For any invoice change before finalization:
- Capture before/after values for qty, weight, price, discount, tax
- Capture user and timestamp
- Capture reason when manually edited

On finalization:
- Freeze calculation inputs and totals
- Persist a PDF/render snapshot hash (future enhancement)

On reset-to-draft:
- Capture before/after invoice status
- Capture before/after `invoice_line_status`
- Capture reason code, note, actor, timestamp

---

## Test Cases (Minimum)
1. Piece-only invoice
2. Catch-weight-only invoice
3. Mixed invoice (piece + per-kg)
4. Catch-weight line missing actual weight (must block)
5. Discount + tax rounding edge cases
6. Large quantity precision case
