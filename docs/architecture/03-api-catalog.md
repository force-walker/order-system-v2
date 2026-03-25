# 03. API Catalog (Screen Responsibility Mapping)

Date: 2026-03-21
Status: Draft for implementation handoff

## Purpose
Define API endpoints mapped to screen responsibilities so implementation tickets can be created directly.

## Base Rules
- Base path: `/api/v1`
- AuthN/AuthZ: JWT + RBAC
- Error families: `400/401/403/404/409/422`
- Transition APIs are explicit user-triggered bulk operations.

---

## 1) Screen: Order List / Search

### Responsibility
- Search orders by status/date/customer
- Open order detail

### APIs
- `GET /orders`
  - Query (examples): `status`, `fromDate`, `toDate`, `customerId`, `page`, `pageSize`
  - Returns: paginated order summaries
- `GET /orders/{orderId}`
  - Returns: order header + summary

---

## 2) Screen: Order Entry / Edit

### Responsibility
- Create/edit order header
- Add/edit/cancel order lines
- Confirm order

### APIs
- `POST /orders`
- `PATCH /orders/{orderId}`
- `GET /orders/{orderId}/items`
- `POST /orders/{orderId}/items`
- `PATCH /orders/{orderId}/items/{itemId}`
- `POST /orders/{orderId}/items/{itemId}/cancel`
- `POST /orders/{orderId}/confirm`
- `POST /orders/{orderId}/cancel`

---

## 3) Screen: Allocation Workbench

### Responsibility
- Run allocation job
- Review allocation by supplier/customer/product views
- Apply manual overrides and split lines

### APIs
- `POST /allocations/runs`
- `GET /allocations`
  - Query (examples): `view=supplier|customer|product`, `orderId`, `supplierId`, `status`
- `PATCH /allocations/{allocationId}`
- `POST /allocations/{allocationId}/split`

---

## 4) Screen: Purchase Result Entry

### Responsibility
- Register supplier purchase outcomes
- Bulk update purchase results

### APIs
- `GET /purchase-results`
- `POST /purchase-results`
- `PATCH /purchase-results/{resultId}`
- `POST /purchase-results/bulk-upsert`

---

## 5) Screen: Transition Operations (Bulk)

### Responsibility
- Execute lifecycle transitions by explicit user action

### APIs
- `POST /transitions/orders/confirmed-to-allocated`
- `POST /transitions/orders/allocated-to-purchased`
- `POST /transitions/orders/purchased-to-shipped`
- `POST /transitions/orders/shipped-to-invoiced`

### Common I/O
Request:
```json
{
  "orderIds": [1001, 1002]
}
```
Response:
```json
{
  "requestedOrderCount": 2,
  "updatedLineCount": 135,
  "updatedOrderCount": 2
}
```
Error note:
- If no eligible target lines are updated: `409 STATUS_NO_TARGET_LINES`

---

## 6) Screen: Invoice Management

### Responsibility
- Generate invoice drafts
- Edit/finalize/reset/unlock invoice
- Maintain invoice lines

### APIs
- `POST /invoices/generate`
- `GET /invoices`
- `GET /invoices/{invoiceId}`
- `PATCH /invoices/{invoiceId}`
- `POST /invoices/{invoiceId}/finalize`
- `POST /invoices/{invoiceId}/reset-to-draft`
- `POST /invoices/{invoiceId}/unlock`
- `GET /invoices/{invoiceId}/items`
- `PATCH /invoices/{invoiceId}/items/{itemId}`

Validation note:
- Catch-weight lines require `actual_weight_kg` before finalize.

---

## 7) Screen: Master Management

### Responsibility
- Maintain products/customers

### APIs
- `GET /products`
- `GET /products/{productId}`
- `POST /products`
- `PATCH /products/{productId}`
- `GET /customers`
- `GET /customers/{customerId}`
- `POST /customers`
- `PATCH /customers/{customerId}`

---

## 8) Screen: Audit / Operations

### Responsibility
- Search audit trail
- Basic operational checks

### APIs
- `GET /audit-logs`
- `GET /health`
- `GET /metrics` (internal/ops use)

---

## 9) Endpoint-to-Role Summary (high level)

- Order Entry role:
  - order create/edit/confirm, line edit/cancel
- Buyer role:
  - allocation run/review/override, purchase result entry, transitions to shipped
- Billing role:
  - invoice generate/finalize/reset (as permitted), shipped->invoiced transition
- Admin role:
  - full access including unlock and critical overrides

(Exact endpoint-level policy follows `api-authorization-spec-draft.md` and RBAC docs.)

---

## 10) Batch API Finalization (Agreed)

### A. Execution mode
- `POST /api/v1/allocations/runs` is **asynchronous** (`202 Accepted` + `jobId`).
- Worker processes allocation jobs out-of-band.

### B. Job APIs
- `POST /api/v1/allocations/runs` (enqueue)
- `GET /api/v1/batch/jobs/{jobId}` (status/progress/result)
- `GET /api/v1/batch/jobs` (list/filter for operations)
- `POST /api/v1/batch/jobs/{jobId}/cancel` (optional but adopted)

### C. Job states
- `queued -> running -> succeeded | failed | cancelled`

### D. Retry policy (MVP)
- Auto retry: **1 time only**
- Retry targets: transient failures only (timeout/temporary connectivity)
- No auto retry for business validation failures
- Retry interval: 30-60 seconds

### E. Concurrency control
- If same `jobType + businessDate` already has `queued` or `running`, reject new start:
  - `409 JOB_ALREADY_RUNNING`

### F. Result payload (summary)
```json
{
  "jobId": "job_01H...",
  "status": "succeeded",
  "traceId": "trc_01H...",
  "summary": {
    "requestedCount": 1200,
    "processedCount": 1180,
    "succeededCount": 1100,
    "failedCount": 50,
    "skippedCount": 30,
    "retryCount": 1,
    "durationMs": 84231,
    "startedAt": "2026-03-25T12:00:00Z",
    "finishedAt": "2026-03-25T12:01:24Z"
  },
  "errors": []
}
```

### G. Audit/Observability required fields
- Required in job logs/events:
  - `jobId`, `traceId`, `requestId`, `actor`, `status`, `startedAt`, `finishedAt`, `durationMs`
- `cancel` and `retry` operations must be audit-logged.

## 11) References
- `docs/architecture/02-status-model.md`
- `docs/openapi-mvp-skeleton-draft.yaml`
- `docs/api-authorization-spec-draft.md`
- `docs/api-error-codes-draft.md`
- `docs/architecture/07-observability.md`
