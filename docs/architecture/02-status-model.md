# 02. Status Model (Implementation Spec from Fixed Requirements)

Date: 2026-03-21
Status: Aligned (No new requirement decision)

## Purpose
This document translates already-fixed requirement policies into implementation-level rules.
It does not redefine requirement scope.

## 1) Canonical Statuses (Fixed)

### Order status
`new -> confirmed -> allocated -> purchased -> shipped -> invoiced` (+ `cancelled`)

### Line status
`open -> allocated -> purchased -> shipped -> invoiced` (+ `cancelled`)

### Transition execution policy
- Line status updates first.
- Order-level transition is executed only by explicit user-triggered bulk action.
- Automatic order promotion from line aggregation is not used in MVP.
- Same-day repeated transition runs are allowed.
- If no eligible target lines are updated, return `409 STATUS_NO_TARGET_LINES`.

## 2) API I/O and Error Semantics (Implementation)

### Target APIs
- `POST /api/v1/transitions/orders/confirmed-to-allocated`
- `POST /api/v1/transitions/orders/allocated-to-purchased`
- `POST /api/v1/transitions/orders/purchased-to-shipped`
- `POST /api/v1/transitions/orders/shipped-to-invoiced`

### Common request
```json
{
  "orderIds": [1001, 1002]
}
```
Rules:
- `orderIds` required
- at least one id

### Common success response
```json
{
  "requestedOrderCount": 2,
  "updatedLineCount": 135,
  "updatedOrderCount": 2
}
```

### Common error families
- `400` invalid request
- `401` unauthenticated
- `403` forbidden
- `404` not found
- `409` transition conflict (including `STATUS_NO_TARGET_LINES`)
- `422` business validation failure

## 3) DB Constraint Responsibility Boundary

### Enforced in DB (hard constraints)
- PK / FK / UNIQUE
- Numeric positivity checks (e.g., `ordered_qty > 0`)
- Pricing-basis check:
  - `pricing_basis=uom_count` => `unit_price_uom_count` required
  - `pricing_basis=uom_kg` => `unit_price_uom_kg` required

### Enforced in Application (workflow constraints)
- Role-based transition permissions
- Eligibility checks across related records
- Finalization prerequisites (including catch-weight checks)
- Multi-entity consistency rules beyond single-row constraints

## 4) Audit Logging (Required Fields and Granularity)

This is detailed implementation of the architecture-level observability/audit policy.
No conflict with system-context decisions.

### Required fields
- `entity_type`
- `entity_id`
- `action`
- `before_json`
- `after_json`
- `reason_code` (required for specific actions)
- `changed_by`
- `changed_at`
- correlation ids: `trace_id`, `request_id`, `job_id` (if batch)

### Mandatory audited actions
- `cancel`
- `override`
- `reset_to_draft`
- `unlock`
- `status_change`

### Granularity policy
- Default: one audit event per business operation.
- For bulk operations: keep a header-level operation event + per-target detail events as needed for traceability.

## 5) Idempotency and Re-run Behavior

### Re-run policy
- Same-day repeated transition execution is allowed.
- Already-transitioned lines are skipped (no duplicate effect).
- If updated target count is zero, return `409 STATUS_NO_TARGET_LINES`.

### Concurrency policy
- Use optimistic concurrency control (`updated_at` or version column).
- If stale update is detected, return conflict (`409`) and require client refresh/retry.

## 6) Alignment References
- `docs/requirements-definition-closure-v2.md`
- `docs/status-transition-draft.md`
- `docs/invoice-lock-and-concurrency-draft.md`
- `docs/api-error-codes-draft.md`
