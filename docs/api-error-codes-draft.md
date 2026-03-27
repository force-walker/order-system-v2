# API Error Codes & 409/422 Policy (MVP)

Updated: 2026-03-27
Status: Draft (current runtime aligned)

## 1. Standard Error Response (current runtime)

```json
{
  "detail": {
    "code": "ORDER_STATUS_MISMATCH",
    "message": "order status mismatch"
  }
}
```

Required fields:
- `detail.code` (string, stable)
- `detail.message` (string)

---

## 2. HTTP Status Usage Policy (finalized for MVP)

- `401 Unauthorized`: missing/invalid/expired bearer token
- `403 Forbidden`: authenticated but permission denied
- `404 Not Found`: target resource does not exist
- `409 Conflict`: **business state conflict**
- `422 Unprocessable Entity`: **input / validation error**

### 2.1 409 vs 422 Decision Rule

Use **422** when request payload itself is invalid:
- required field missing
- enum value invalid
- invalid field range / relation (e.g., `due_date < invoice_date`)
- invalid transition pair (e.g., unsupported `from_status -> to_status`)

Use **409** when payload is valid but server-side state conflicts:
- duplicate key/resource already exists
- status mismatch with current resource state
- lock-state mismatch
- concurrent/running job conflict

---

## 3. Error Code Catalog (current runtime)

### 3.1 401
- `AUTH_REQUIRED`

### 3.2 403
- `FORBIDDEN`

### 3.3 404
- `PRODUCT_NOT_FOUND`
- `CUSTOMER_NOT_FOUND`
- `ORDER_NOT_FOUND`
- `INVOICE_NOT_FOUND`
- `ALLOCATION_NOT_FOUND`
- `RESOURCE_NOT_FOUND`

### 3.4 409 (state conflict)
- `SKU_ALREADY_EXISTS`
- `CUSTOMER_CODE_ALREADY_EXISTS`
- `ORDER_NO_ALREADY_EXISTS`
- `INVOICE_NO_ALREADY_EXISTS`
- `ORDER_STATUS_MISMATCH`
- `STATUS_NO_TARGET_LINES`
- `INVOICE_NOT_DRAFT`
- `INVOICE_NOT_FINALIZED`
- `INVOICE_NOT_LOCKED_FINALIZED`
- `JOB_ALREADY_RUNNING`
- `RETRY_NOT_ALLOWED`
- `RETRY_LIMIT_EXCEEDED`

### 3.5 422 (input/validation)
- `INVALID_TRANSITION_PAIR`
- `INVALID_DATE_RANGE`
- `INVALID_ROLE`
- FastAPI/Pydantic validation errors (missing required, enum/type mismatch, etc.)

---

## 4. Endpoint Mapping (key examples)

### Auth
- `POST /api/v1/auth/login`
  - `422 INVALID_ROLE` (invalid role input)
- `GET /api/v1/auth/me`
  - `401 AUTH_REQUIRED`

### Products / Customers
- create duplicate: `409`
- required/enum/type invalid: `422`

### Orders
- `POST /api/v1/orders/{order_id}/bulk-transition`
  - unsupported pair / same status: `422 INVALID_TRANSITION_PAIR`
  - order current status mismatch: `409 ORDER_STATUS_MISMATCH`
  - no eligible lines: `409 STATUS_NO_TARGET_LINES`

### Invoices
- `POST /api/v1/invoices`
  - `due_date < invoice_date`: `422 INVALID_DATE_RANGE`
  - duplicate invoice no: `409 INVOICE_NO_ALREADY_EXISTS`
- finalize/reset/unlock invalid current status: `409`

### Batch
- `POST /api/v1/allocations/runs`
  - same business date already queued/running: `409 JOB_ALREADY_RUNNING`
- retry non-failed or over retry limit: `409`

---

## 5. DB Constraint Exception Mapping (centralized)

To reduce endpoint-by-endpoint variance, DB integrity exceptions are centrally mapped:

- Unique violation (`23505`, UNIQUE failed) -> `409 RESOURCE_ALREADY_EXISTS`
- FK violation (`23503`) -> `422 INVALID_REFERENCE`
- Check violation (`23514`, CHECK failed) -> `422 VALIDATION_FAILED`
- Not-null / length violations (`23502`, `22001`) -> `422 VALIDATION_FAILED`
- Other integrity violations -> `409 CONSTRAINT_VIOLATION`

This mapping is implemented in `backend/app/core/exception_mapping.py` and wired globally in `app/main.py`.

## 6. Testing & Governance

- Runtime behavior is enforced by:
  - endpoint tests in `backend/tests/*`
  - OpenAPI contract tests (`backend/tests/test_openapi_contract_api.py`)
  - policy test (`backend/tests/test_error_policy_409_422_api.py`)
- When adding new endpoints:
  1. classify each failure path as 409 or 422 by this policy
  2. expose status codes in OpenAPI `responses`
  3. add/extend tests for both negative paths
