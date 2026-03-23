# Requirements Definition Closure v2.0 (MVP)

Date: 2026-03-17
Status: Closed for MVP implementation handoff

## 1) Closure declaration
MVP requirements definition is closed.
All previously open high-priority items (status terminology, enum unification, transition boundaries, cancel/reset/unlock boundaries, error semantics, UAT execution baseline) are fixed for implementation.

## 2) Final fixed policies (delta from v1)

### A. Status / Transition
- Canonical order status:
  - `new -> confirmed -> allocated -> purchased -> shipped -> invoiced` (+ `cancelled`)
- Canonical line status:
  - `open -> allocated -> purchased -> shipped -> invoiced` (+ `cancelled`)
- Order-level transition runs are user-triggered bulk actions only.
- Same-day repeated transition runs are allowed.
- Automatic order status promotion from line aggregation is not used in MVP.
- If no eligible lines are found in transition run: `409 STATUS_NO_TARGET_LINES`.

### B. Enum / Terminology
- `stockout_policy`: `backorder | substitute | cancel | split`
- `override_reason_code`: optional
- `reset_reason_code`: required (`data_error|pricing_error|tax_error|customer_change|policy_exception`)
- `unlock_reason_code`: required (`pricing_correction|quantity_correction|tax_correction|customer_request|data_fix|other`)
- UOM/pricing naming unified:
  - `uom_count / uom_kg`
  - `unit_price_uom_count / unit_price_uom_kg`

### C. Cancel / Reset / Unlock boundaries
- Cancel:
  - `line_status` and `invoice_line_status` are updated together.
  - Bulk cancel is manual only (explicit user input), not automatic.
- Reset-to-draft:
  - Target only when `invoice.status=finalized`.
  - `invoice.status: finalized -> draft`
  - affected `invoice_line_status` reset to `uninvoiced`.
- Unlock:
  - Target only finalized+locked invoice.
  - Admin only.
  - `unlock_reason_code` required, `reason_note` optional (<=500 chars).
  - TTL unlimited; no auto re-lock; re-finalize to freeze again.

### D. Error semantics
- Standardized status families: `400/401/403/404/409/422`
- Added transition no-target conflict:
  - `STATUS_NO_TARGET_LINES`

### E. UAT execution baseline (fixed)
- Concurrent users: 10
- Dataset:
  - orders 10,000
  - order_lines 100,000
  - invoices 30,000
- Performance targets:
  - API P95 <= 1.5s
  - Grid initial view P95 <= 2.0s
  - Allocation batch 5,000 lines <= 5 min

## 3) Source-of-truth package (for implementation)
Primary references:
- `docs/report-and-api-io-definition-draft.md`
- `docs/status-transition-draft.md`
- `docs/invoice-rules-draft.md`
- `docs/invoice-lock-and-concurrency-draft.md`
- `docs/api-error-codes-draft.md`
- `docs/openapi-error-components-draft.yaml`
- `docs/openapi-mvp-skeleton-draft.yaml`
- `docs/uat-acceptance-checklist-draft.md`
- `docs/decision_logs.txt`

## 4) Deferred items (out of MVP)
- Automatic order split for unfinished lines (future enhancement)
- Fine-grained post-unlock editable-field restrictions
- Advanced audit analytics UI (beyond CSV export)
- Accounting scope additions (e.g., `paid` status)

## 5) Implementation handoff gate
Handoff is considered complete when:
1. OpenAPI + error codes + UAT checklist are checked in and aligned
2. No unresolved contradiction in decision logs
3. Implementation bootstrap plan is accepted
