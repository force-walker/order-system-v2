# Spec Alignment Log — IO v2 Baseline

Date: 2026-03-14
Baseline: `docs/IO_from_order_to_invoice_revised_v_2.xlsx`

## Updated files
- `docs/report-and-api-io-definition-draft.md`
- `docs/db-dual-uom-draft.md`
- `docs/status-transition-draft.md`

## Applied alignments

### 1) Governance / source-of-truth
- Added explicit rule that IO definition source-of-truth is `IO_from_order_to_invoice_revised_v_2.xlsx`.

### 2) Vocabulary alignment
- Added normalized vocab sections:
  - Direction: `input | derived | generated | validation | output_rule`
  - Entry Method: `manual | lookup_select | auto_default | auth_context | system_timestamp | rule_engine | calculated | n/a`

### 3) Order Create expansion
- Added/clarified fields aligned to v2 matrix:
  - `customer_name`, `customer_address`
  - `billing_customer_id`, `billing_address`
  - `order_status`, `order_source`, `cutoff_datetime`
  - `created_at/created_by`, `updated_at/updated_by`
  - `items[].line_status`

### 4) Cutoff change policy
- Added dedicated section for post-cutoff update controls:
  - `change_reason`
  - `procurement_list_regeneration`
  - `allocation_preservation_on_regeneration`
- Added transition doc rules: post-cutoff edits limited to creator/admin + reason/audit requirement.

### 5) Invoice/Purchase detail expansion
- Added invoice header fields in API draft:
  - `invoice_customer_id`, `invoice_customer_name`, `invoice_customer_address`
  - `payment_terms`, `due_date`, `tax_rate`, `tax_amount`, `total_amount_pretax`, `total_amount`
- Added billable quantity basis note (`billable_qty`/`billable_uom`).
- Expanded DB draft purchase results with:
  - `transport_cost`, `final_billable_qty`, `final_billable_uom`, `invoiceable_flag`, `invoice_block_reason`
- Expanded DB draft invoice items with:
  - `billable_qty`, `billable_uom`, `line_amount`, `discount`, `line_tax_amount`

## Notes
- This alignment pass keeps existing MVP status policy (`... -> invoiced` terminal).
- Detailed row-level authority and lock controls remain governed by the IO matrix and should be used in implementation tickets.
