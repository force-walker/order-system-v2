# ADR-0006: Minimum Observability Baseline

- Status: Accepted
- Date: 2026-03-22

## Context
Need fast detection of API/batch/DB problems without overengineering initial platform.

## Decision
Adopt MVP observability baseline:
- Structured logs with correlation IDs (`trace_id`, `request_id`, `job_id`)
- Minimum metrics for API/Worker/DB
- Initial alert thresholds for 5xx rate, p95 latency, worker failure/backlog, DB saturation
- Initial dashboards: API health, Worker health, DB load

## Consequences
- Pros: practical incident response readiness from MVP.
- Cons: threshold tuning needed after real traffic.

## References
- `docs/architecture/07-observability.md`
- `docs/architecture/01-system-context.md`
