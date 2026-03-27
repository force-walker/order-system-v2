# 08. Audit API Specification (MVP)

Date: 2026-03-26
Status: Draft for implementation handoff

## Purpose
Define read-focused, immutable audit APIs for incident investigation, compliance checks, and operational traceability.

## Principles
- Audit logs are append-only (no update/delete API).
- Searchability first: period + actor + action + entity + trace correlation.
- Sensitive values must be masked/minimized in responses.

---

## 1) API Endpoints

### 1.1 Search audit logs
- `GET /api/v1/audit-logs`

Query parameters (recommended):
- `from` (ISO8601 datetime)
- `to` (ISO8601 datetime)
- `actorId`
- `action` (`cancel|override|status_change|reset_to_draft|unlock|create|update`)
- `entityType` (`order|order_item|allocation|purchase_result|invoice|invoice_item|job`)
- `entityId`
- `traceId`
- `jobId`
- `page` (default 1)
- `pageSize` (default 50, max 200)
- `sort` (`occurredAt:asc|desc`, default `desc`)

Use case:
- primary investigation/search API for UI and operations.

### 1.2 Get single audit log detail
- `GET /api/v1/audit-logs/{auditLogId}`

Use case:
- fetch full before/after payload and metadata for one event.

### 1.3 Entity timeline
- `GET /api/v1/audit-logs/entities/{entityType}/{entityId}`

Query parameters:
- `from`, `to`, `page`, `pageSize`, `sort`

Use case:
- view event history for one order/invoice/allocation etc.

### 1.4 Export (optional but recommended)
- `POST /api/v1/audit-logs/export`

Request (example):
```json
{
  "from": "2026-03-01T00:00:00Z",
  "to": "2026-03-31T23:59:59Z",
  "action": ["cancel", "unlock"],
  "entityType": ["invoice"],
  "format": "csv"
}
```

Response:
- async export job id or signed download URL (implementation choice)

---

## 2) Response Model

## 2.1 AuditLog item
```json
{
  "id": 987654,
  "occurredAt": "2026-03-26T02:00:05Z",
  "actor": {
    "id": "u_1001",
    "name": "buyer_a",
    "role": "buyer"
  },
  "action": "status_change",
  "entityType": "order_item",
  "entityId": 554433,
  "reasonCode": null,
  "before": {"line_status": "allocated"},
  "after": {"line_status": "purchased"},
  "traceId": "trc_01H...",
  "requestId": "req_01H...",
  "jobId": "job_01H...",
  "source": "worker"
}
```

## 2.2 Search response
```json
{
  "items": [],
  "page": 1,
  "pageSize": 50,
  "total": 1234
}
```

---

## 3) Mandatory Captured Fields (write-side requirement)

Audit events must include:
- `entityType`
- `entityId`
- `action`
- `before`
- `after`
- `reasonCode` (required for designated operations)
- `actor.id`
- `occurredAt`
- `traceId`
- `requestId`
- `jobId` (if batch)
- `source` (`api|worker|system`)

Mandatory audited actions (standardized action vocabulary):
- generic: `create`, `update`
- order flow: `bulk_transition`
- invoice flow: `finalize`, `reset_to_draft`, `unlock`
- allocation flow: `override`, `split_line`
- purchase-result flow: `bulk_upsert_create`, `bulk_upsert_update`
- batch flow: `enqueue`, `start`, `complete`, `cancel`, `retry`

Actor policy:
- API endpoints without auth context use actor=`system_api`
- Auth-required endpoints should write authenticated user id into actor

---

## 4) Authorization Policy

- Default read access: `admin`
- Optional scoped read access (future/controlled): `billing`, `buyer` with filtered scope
- No write/update/delete endpoints for audit records

---

## 5) Error Model

Use unified error response (`code`, `message`, `details`, `traceId`).

- `400` invalid filter format
- `401` unauthorized
- `403` forbidden
- `404` audit record not found
- `422` invalid date range (`from > to`)
- `500` internal error

Recommended error codes:
- `INVALID_REQUEST_FORMAT`
- `MISSING_REQUIRED_FIELD`
- `AUTH_REQUIRED`
- `AUTH_FORBIDDEN`
- `RESOURCE_NOT_FOUND`
- `VALIDATION_FAILED`
- `INTERNAL_ERROR`

---

## 6) Operational Notes

- Retention: at least 13 months (per non-functional policy).
- PII masking: avoid returning sensitive values directly in `before/after` when not necessary.
- Indexing recommendation:
  - `(occurred_at desc)`
  - `(entity_type, entity_id, occurred_at desc)`
  - `(actor_id, occurred_at desc)`
  - `(trace_id)`
  - `(job_id)`

---

## 7) References
- `docs/architecture/07-observability.md`
- `docs/architecture/06-error-model.md`
- `docs/architecture/05-authn-authz.md`
- `docs/non-functional-requirements-draft.md`
