# Frontend Handoff: API Contract Freeze (MVP)

Updated: 2026-03-27
Status: **Frozen for mockup phase**

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
- `PATCH /api/v1/purchase-results/{result_id}`
- `POST /api/v1/purchase-results/bulk-upsert`

### Invoices
- `POST /api/v1/invoices`
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

---

## 4) Freeze policy

Until mockup completion:
- No request/response field rename/removal.
- No status code semantic changes.
- Any unavoidable contract change must:
  1. update OpenAPI doc,
  2. update regression tests,
  3. include migration note for frontend.
