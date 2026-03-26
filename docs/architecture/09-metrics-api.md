# 09. Metrics API Specification (MVP)

Date: 2026-03-26
Status: Draft for implementation handoff

## Purpose
Define MVP metrics APIs for operational visibility of API, Worker/Batch, and DB health.

## Principles
- Metrics endpoint is for internal/ops usage only.
- Keep metric set minimal but actionable.
- Align with observability baseline and alert rules.

---

## 1) API Endpoints

### 1.1 Prometheus scrape endpoint
- `GET /api/v1/metrics`
- Response: text/plain (Prometheus exposition format)
- Auth: internal-only (network restriction + optional auth)

### 1.2 Metrics summary API (optional for dashboard API consumption)
- `GET /api/v1/ops/metrics/summary`
- Response: JSON summary for UI/admin panels
- Auth: `admin` only

### 1.3 Job metrics API (optional)
- `GET /api/v1/ops/metrics/jobs`
- Response: JSON with queue/backlog/failure metrics
- Auth: `admin` only

---

## 2) Required Metric Set (MVP)

## 2.1 API metrics
- `requests_total` (counter)
- `request_errors_total` (counter, labeled by status family)
- `request_duration_ms` (histogram: p50/p95/p99)
- `inflight_requests` (gauge)

Recommended labels:
- `endpoint`
- `method`
- `status_family`

## 2.2 Worker/Batch metrics
- `jobs_enqueued_total` (counter)
- `jobs_processed_total` (counter)
- `jobs_failed_total` (counter)
- `job_duration_ms` (histogram)
- `queue_backlog` (gauge)
- `job_oldest_age_sec` (gauge)

Recommended labels:
- `job_type`
- `status`

## 2.3 DB metrics
- `db_connections_in_use` (gauge)
- `db_query_duration_ms` (histogram)
- `db_errors_total` (counter)
- `deadlocks_total` (counter, optional)

---

## 3) JSON Summary Response (optional endpoint)

`GET /api/v1/ops/metrics/summary`

```json
{
  "timestamp": "2026-03-26T03:00:00Z",
  "api": {
    "requestsTotal": 120034,
    "errorRate5xx": 0.012,
    "p95LatencyMs": 780,
    "inflightRequests": 14
  },
  "worker": {
    "enqueuedTotal": 1200,
    "processedTotal": 1188,
    "failedTotal": 12,
    "backlog": 3,
    "oldestAgeSec": 40
  },
  "db": {
    "connectionsInUse": 18,
    "queryP95Ms": 120,
    "errorsTotal": 0,
    "deadlocksTotal": 0
  }
}
```

---

## 4) Alert Mapping (from metrics)

## API alerts
- 5xx rate > 2% for 5 minutes
- p95 latency > 1000ms for 10 minutes

## Worker alerts
- failure rate > 5% for 10 minutes
- queue backlog keeps increasing for 15 minutes
- `job_oldest_age_sec` > 900

## DB alerts
- connection usage > 80% for 5 minutes
- repeated connection timeout/error events

---

## 5) Security / Exposure Policy

- `/api/v1/metrics` should not be public internet endpoint.
- Prefer allowlisted network path (Prometheus/VPN/internal ingress).
- If exposed via app gateway, require auth and rate limiting.
- Never include sensitive business payload values in metrics labels.

---

## 6) Error Model

For JSON metrics endpoints (`/ops/metrics/*`), use standard error model:
- `400` invalid query parameter
- `401/403` unauthorized/forbidden
- `500` internal aggregation error

Codes (examples):
- `INVALID_REQUEST_FORMAT`
- `AUTH_REQUIRED`
- `AUTH_FORBIDDEN`
- `INTERNAL_ERROR`

---

## 7) Implementation Notes

- Use low-cardinality labels only.
- Keep histogram buckets stable after initial release.
- Ensure worker process publishes metrics independently.
- Correlate spikes using `traceId`/`jobId` from logs.

---

## 8) References
- `docs/architecture/07-observability.md`
- `docs/architecture/08-audit-api.md`
- `docs/non-functional-requirements-draft.md`
