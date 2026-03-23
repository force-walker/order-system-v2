# ADR-0001: MVP Architecture Baseline

- Status: Accepted
- Date: 2026-03-22

## Context
Need a practical baseline to restart development with low risk and clear operational boundaries.

## Decision
Adopt MVP baseline:
- Frontend SPA
- Backend API (`/api/v1`)
- Worker/Batch as **separate process**
- PostgreSQL as system-of-record
- Structured logs + minimum metrics from day 1

## Consequences
- Pros: clear separation of online vs batch workloads, easier scaling/ops.
- Cons: additional deployment/runtime management for worker process.

## References
- `docs/architecture/01-system-context.md`
- `docs/architecture/07-observability.md`
