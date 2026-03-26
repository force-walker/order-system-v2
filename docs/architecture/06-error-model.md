# 06. Error Model (MVP)

Date: 2026-03-21
Status: Draft for implementation handoff

## Purpose
Define a unified error response model and status/code mapping for all MVP APIs.

## 1) Standard Error Response

All non-2xx API responses must follow:

```json
{
  "code": "STATUS_NO_TARGET_LINES",
  "message": "No eligible lines for transition.",
  "details": {
    "orderIds": [1001, 1002]
  },
  "traceId": "trc_01HXYZ..."
}
```

Fields:
- `code` (string): stable machine-readable error code
- `message` (string): human-readable summary
- `details` (object): optional structured context
- `traceId` (string): correlation id for troubleshooting

---

## 2) HTTP Status Families (MVP)

- `401 Unauthorized`
  - missing/invalid/expired access token
- `403 Forbidden`
  - authenticated but insufficient permission
- `404 Not Found`
  - target resource not found
- `409 Conflict`
  - **business state conflict** (duplicate, status mismatch, lock mismatch, concurrency conflict)
- `422 Unprocessable Entity`
  - **input/validation failure** (required/enum/type/range/invalid transition pair)

### 2.1 409 / 422 判定ルール（運用固定）

- 422: 入力不正（必須不足、enum不正、日付範囲不正、不正な遷移ペア）
- 409: 業務状態競合（重複、状態不一致、ロック不一致、同時実行衝突）

---

## 3) Core Business Error Codes

### Transition / lifecycle
- `STATUS_NO_TARGET_LINES`
  - No eligible lines updated in transition run
  - HTTP: `409`
- `STATUS_TRANSITION_CONFLICT`
  - Current state does not satisfy transition preconditions
  - HTTP: `409`
- `STATUS_STALE_VERSION`
  - Optimistic concurrency conflict
  - HTTP: `409`

### Validation
- `VALIDATION_FAILED`
  - Generic validation failure
  - HTTP: `422`
- `CATCH_WEIGHT_MISSING_ACTUAL_WEIGHT`
  - finalize attempted without `actual_weight_kg`
  - HTTP: `422`
- `PRICE_BASIS_FIELD_MISSING`
  - required unit price missing for selected pricing basis
  - HTTP: `422`

### Auth/AuthZ
- `AUTH_TOKEN_INVALID`
  - HTTP: `401`
- `AUTH_TOKEN_EXPIRED`
  - HTTP: `401`
- `AUTH_FORBIDDEN`
  - HTTP: `403`

### Resource
- `RESOURCE_NOT_FOUND`
  - HTTP: `404`
- `RESOURCE_ALREADY_EXISTS`
  - HTTP: `409`

### System/Internal
- `INTERNAL_ERROR`
  - unexpected internal failure
  - HTTP: `500`

---

## 4) Endpoint Mapping Rules

### Transition endpoints
- `POST /transitions/orders/*`
  - no eligible targets: `409 STATUS_NO_TARGET_LINES`
  - state mismatch: `409 STATUS_TRANSITION_CONFLICT`
  - role violation: `403 AUTH_FORBIDDEN`

### Invoice finalize/reset/unlock
- finalize catch-weight missing: `422 CATCH_WEIGHT_MISSING_ACTUAL_WEIGHT`
- invalid state: `409 STATUS_TRANSITION_CONFLICT`
- unlock non-admin: `403 AUTH_FORBIDDEN`

### Master/order input
- invalid payload: `400` or `422` (prefer `422` for business rule checks)
- duplicate key (order_no/sku/invoice_no): `409 RESOURCE_ALREADY_EXISTS`

---

## 5) Validation Error Detail Format

For field-level validation, `details` should include field issues:

```json
{
  "code": "VALIDATION_FAILED",
  "message": "Validation failed.",
  "details": {
    "fields": [
      {"name": "unit_price_uom_kg", "reason": "required_when_pricing_basis_is_uom_kg"}
    ]
  },
  "traceId": "trc_01HXYZ..."
}
```

---

## 6) Logging and Observability Requirements

When returning an error response:
- include `traceId` in response
- write structured error log with:
  - `trace_id`, `request_id`, `job_id` (if batch)
  - `code`, `http_status`, `endpoint`, `actor`, `resource`

Do not expose internal stack traces to clients.

---

## 7) Implementation Notes

- Keep error codes centralized in a single module/enum.
- Keep OpenAPI error components synchronized with this document.
- Use stable code naming; avoid changing existing codes once published.

---

## 8) References
- `docs/api-error-codes-draft.md`
- `docs/openapi-error-components-draft.yaml`
- `docs/architecture/02-status-model.md`
- `docs/architecture/03-api-catalog.md`
- `docs/architecture/07-observability.md`
