# Frontend Handoff: API Contract Freeze (MVP)

Updated: 2026-04-06
Status: **Frozen for phase2 UI/API integration**

Purpose:
- Freeze API contract during frontend mockup implementation.
- Prevent avoidable rework from backend contract drift.

## 1) Source of truth

- Runtime-aligned OpenAPI: `docs/openapi-mvp-skeleton-draft.yaml`
- Error model: `docs/api-error-codes-draft.md`
- 409/422 policy: `docs/architecture/06-error-model.md`

During mockup phase, frontend should implement against these only.

---

## 2) Frozen endpoint scope for mockup

### Auth
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `GET /api/v1/auth/me`

### Master
- `GET /api/v1/products`
- `GET /api/v1/products/{product_id}`
- `POST /api/v1/products`
- `PATCH /api/v1/products/{product_id}`
- `GET /api/v1/customers`
- `GET /api/v1/customers/{customer_id}`
- `POST /api/v1/customers`
- `PATCH /api/v1/customers/{customer_id}`

### Orders / Allocations / Purchase Results
- `GET /api/v1/orders`
- `GET /api/v1/orders/{order_id}`
- `POST /api/v1/orders`
- `POST /api/v1/orders/{order_id}/bulk-transition`
- `PATCH /api/v1/allocations/{allocation_id}/override`
- `POST /api/v1/allocations/{allocation_id}/split-line`
- `POST /api/v1/purchase-results`
- `GET /api/v1/purchase-results`
- `GET /api/v1/purchase-results/{result_id}`
- `PATCH /api/v1/purchase-results/{result_id}`
- `POST /api/v1/purchase-results/bulk-upsert`

### Invoices
- `GET /api/v1/invoices`
- `GET /api/v1/invoices/{invoice_id}`
- `GET /api/v1/invoices/{invoice_id}/items`
- `POST /api/v1/invoices`
- `POST /api/v1/invoices/generate`
- `POST /api/v1/invoices/{invoice_id}/finalize`
- `POST /api/v1/invoices/{invoice_id}/reset-to-draft`
- `POST /api/v1/invoices/{invoice_id}/unlock`

### Batch / Audit / Metrics
- `POST /api/v1/allocations/runs`
- `GET /api/v1/batch/jobs`
- `GET /api/v1/batch/jobs/{job_id}`
- `POST /api/v1/batch/jobs/{job_id}/cancel`
- `POST /api/v1/batch/jobs/{job_id}/retry`
- `GET /api/v1/audit-logs`
- `GET /api/v1/audit-logs/{auditLogId}`
- `GET /api/v1/audit-logs/entities/{entityType}/{entityId}`
- `GET /api/v1/ops/metrics/summary`

---

## 3) Frozen response/error conventions

- Error payload shape:
  - `detail.code`
  - `detail.message`
- 422: input validation issues
- 409: business state conflicts

Frontend should parse `detail.code` first for user messaging/branching.

Phase2で優先対応するcode:
- Invoice: `INVOICE_ITEMS_REQUIRED`, `INVOICE_NOT_DRAFT`, `INVOICE_NOT_LOCKED_FINALIZED`, `INVOICE_NO_ALREADY_EXISTS`, `ORDER_ITEMS_NOT_FOUND`, `MISSING_ACTUAL_WEIGHT`, `MISSING_UNIT_PRICE`
- Order transition: `ORDER_STATUS_MISMATCH`, `LINE_STATUS_MISMATCH`, `INVALID_TRANSITION_PAIR`
- Purchase: `PURCHASE_QTY_EXCEEDS_ALLOCATION`, `ALLOCATION_NOT_FOUND`

---

## 4) Freeze policy

Until mockup completion:
- No request/response field rename/removal.
- No status code semantic changes.
- Any unavoidable contract change must:
  1. update OpenAPI doc,
  2. update regression tests,
  3. include migration note for frontend.
