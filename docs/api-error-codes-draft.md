# API Error Codes Draft (MVP)

Updated: 2026-03-18
Status: Draft (endpoint-specific; aligned with current runtime)

## 1. Standard Error Response

```json
{
  "code": "STATUS_NO_TARGET_LINES",
  "message": "no eligible lines"
}
```

Required fields:
- `code` (string, stable)
- `message` (string)

---

## 2. HTTP Status Usage Policy

- `400 Bad Request`: invalid input / missing runtime-required data
- `401 Unauthorized`: missing/invalid bearer token
- `403 Forbidden`: role/scope not allowed
- `404 Not Found`: target resource not found
- `409 Conflict`: state/version/lock conflict
- `422 Unprocessable Entity`: invalid enum/pair/value set

---

## 3. Error Code Catalog (Current Runtime)

### 3.1 400 Bad Request
- `ORDER_WEIGHT_REQUIRED`
- `NO_INVOICEABLE_ITEMS`
- `CATCH_WEIGHT_REQUIRED`
- `UNIT_PRICE_UOM_COUNT_REQUIRED`
- `UNIT_PRICE_UOM_KG_REQUIRED`
- `NEGATIVE_INVOICE_TOTAL`
- `ALLOCATION_INVALID`
- `ALLOCATION_INVALID_TARGET_QTY`
- `SPLIT_QTY_MISMATCH`
- `SPLIT_GROUP_MISSING_PARENT`
- `SPLIT_GROUP_MIN_CHILDREN`
- `SPLIT_GROUP_QTY_MISMATCH`
- `SPLIT_GROUP_UOM_MISMATCH`

### 3.2 401 Unauthorized
- `AUTH_REQUIRED`

### 3.3 403 Forbidden
- `FORBIDDEN`

### 3.4 404 Not Found
- `ORDER_NOT_FOUND`
- `INVOICE_NOT_FOUND`
- `ALLOCATION_NOT_FOUND`
- `RESOURCE_NOT_FOUND`

### 3.5 409 Conflict
- `VERSION_CONFLICT`
- `ORDER_STATUS_MISMATCH`
- `STATUS_NO_TARGET_LINES`
- `INVOICE_NOT_DRAFT`
- `INVOICE_NOT_FINALIZED`
- `INVOICE_NOT_LOCKED_FINALIZED`
- `REGENERATION_IN_PROGRESS`
- `RETRY_NOT_ALLOWED`
- `RETRY_LIMIT_EXCEEDED`

### 3.6 422 Unprocessable Entity
- `INVALID_TRANSITION_PAIR`
- `INVALID_RESET_REASON_CODE`
- `INVALID_UNLOCK_REASON_CODE`

---

## 4. Endpoint-specific Mapping

### Auth
- `POST /api/v1/auth/login`: `403 FORBIDDEN`
- Bearer-required endpoints: `401 AUTH_REQUIRED`

### Orders
- `POST /api/v1/orders/{order_id}/bulk-transition`
  - `404 ORDER_NOT_FOUND`
  - `409 VERSION_CONFLICT`
  - `409 ORDER_STATUS_MISMATCH`
  - `409 STATUS_NO_TARGET_LINES`
  - `422 INVALID_TRANSITION_PAIR`

### Invoices
- `POST /api/v1/invoices`:
  - `404 ORDER_NOT_FOUND`
  - `400 NO_INVOICEABLE_ITEMS`
  - `400 CATCH_WEIGHT_REQUIRED`
  - `400 UNIT_PRICE_UOM_COUNT_REQUIRED`
  - `400 UNIT_PRICE_UOM_KG_REQUIRED`
- `POST /api/v1/invoices/{invoice_id}/finalize`:
  - `404 INVOICE_NOT_FOUND`
  - `400 NEGATIVE_INVOICE_TOTAL`
  - `409 INVOICE_NOT_DRAFT`
- `POST /api/v1/invoices/{invoice_id}/reset-to-draft`:
  - `404 INVOICE_NOT_FOUND`
  - `409 VERSION_CONFLICT`
  - `409 INVOICE_NOT_FINALIZED`
  - `422 INVALID_RESET_REASON_CODE`
- `POST /api/v1/invoices/{invoice_id}/unlock`:
  - `404 INVOICE_NOT_FOUND`
  - `409 VERSION_CONFLICT`
  - `409 INVOICE_NOT_LOCKED_FINALIZED`
  - `422 INVALID_UNLOCK_REASON_CODE`

### Allocations
- `PATCH /api/v1/allocations/{allocation_id}/override`
  - `404 ALLOCATION_NOT_FOUND`
  - `409 VERSION_CONFLICT`
- `POST /api/v1/allocations/{allocation_id}/split-line`
  - `404 ALLOCATION_NOT_FOUND`
  - `409 VERSION_CONFLICT`
  - `400 ALLOCATION_INVALID_TARGET_QTY`
  - `400 SPLIT_QTY_MISMATCH`

### Purchase Results
- `POST /api/v1/purchase-results`
  - `404 ALLOCATION_NOT_FOUND`
- `PATCH /api/v1/purchase-results/{result_id}`
  - `404 RESOURCE_NOT_FOUND`
  - `404 ALLOCATION_NOT_FOUND`
  - `409 VERSION_CONFLICT`
- `POST /api/v1/purchase-results/bulk-upsert`
  - `404 ALLOCATION_NOT_FOUND`
  - `409 VERSION_CONFLICT`

### Batch
- `POST /api/v1/batch/procurement-regeneration`
  - `409 REGENERATION_IN_PROGRESS`
- `POST /api/v1/batch/jobs/{task_id}/retry`
  - `404 RESOURCE_NOT_FOUND`
  - `409 RETRY_NOT_ALLOWED` (failed以外/最新attempt以外)
  - `409 RETRY_LIMIT_EXCEEDED`
  - `409 REGENERATION_IN_PROGRESS`

### Master APIs
- `GET/PATCH /api/v1/products/{product_id}`
  - `404 RESOURCE_NOT_FOUND`
  - `409 VERSION_CONFLICT` (PATCH)
- `GET/PATCH /api/v1/customers/{customer_id}`
  - `404 RESOURCE_NOT_FOUND`
  - `409 VERSION_CONFLICT` (PATCH)

---

## 5. Notes

- This draft matches current runtime behavior (`detail: { code, message }`).
- If response schema is expanded later (`field`, `resource`, `trace_id` etc.), update this file + OpenAPI components together.
