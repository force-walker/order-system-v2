# 07. Observability Policy (MVP)

Date: 2026-03-21
Status: Agreed

## Objective
Provide minimum viable observability for stable operations:
- detect failures quickly
- identify impact scope
- support root-cause analysis

## A. API Metrics (Backend)

Required metrics:
- `requests_total`
- `request_errors_total` (4xx/5xx)
- `request_duration_ms` (p50/p95/p99)
- `inflight_requests`

Minimum alerts:
- 5xx rate > 2% for 5 min
- p95 latency > 1000ms for 10 min

## B. Worker / Batch Metrics

Required metrics:
- `jobs_enqueued_total`
- `jobs_processed_total`
- `jobs_failed_total`
- `job_duration_ms`
- `queue_backlog`
- `job_oldest_age_sec`

Minimum alerts:
- failure rate > 5% for 10 min
- backlog keeps increasing for 15 min
- `job_oldest_age_sec` > 900

## C. Database Metrics (PostgreSQL)

Required metrics:
- `db_connections_in_use`
- `db_query_duration_ms`
- `db_errors_total` (connection/timeout)
- optional: `deadlocks_total`

Minimum alerts:
- connection usage > 80% for 5 min
- repeated timeout/connection errors

## D. Common Logging Rules

1. Correlation fields required in all logs:
- `trace_id`
- `request_id`
- `job_id` (for batch/jobs)

2. Error logs:
- must be JSON structured
- must include error category/code
- include context: actor, endpoint/job, resource id, status

3. Log levels:
- INFO: normal flow and business milestones
- WARN: degraded but recoverable
- ERROR: failed operations requiring intervention

## E. Initial Dashboards (3)

1. API health
- traffic, error rate, latency

2. Worker health
- enqueue/processed/failed, backlog, oldest age

3. DB load
- connections, slow queries, error counts

## F. Notification Routing (MVP)

Use one destination only (Slack/Discord/PagerDuty) for MVP.

Notification targets:
- API 5xx spike
- Worker failure/backlog anomalies
- DB connection/timeouts anomaly

## G. Operational Notes

- Keep cardinality low for labels/tags in early stage.
- Alert thresholds can be tuned after first 1-2 weeks of production telemetry.
- Store enough context to connect app logs, worker logs, and DB events by correlation ids.
