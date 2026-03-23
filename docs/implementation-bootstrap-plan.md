# Implementation Bootstrap Plan (React + FastAPI + PostgreSQL)

Updated: 2026-03-17
Status: Draft for execution kickoff

## 1) Tech Stack
- Frontend: React + TypeScript + MUI + TanStack Query + React Hook Form + Zod
- Backend: FastAPI + SQLAlchemy 2.x + Alembic + Pydantic
- DB: PostgreSQL
- Queue/Batch: Redis + Celery
- Observability: Prometheus + Grafana (+ structured app logs)

## 2) Suggested Folder Structure

```text
order_system/
  frontend/
    src/
      app/
      pages/
      components/
      features/
        orders/
        allocations/
        purchase-results/
        invoices/
      lib/api/
      lib/validation/
      lib/auth/
    tests/
  backend/
    app/
      api/
        v1/
      core/
      models/
      schemas/
      services/
        transitions/
        billing/
        allocation/
      repositories/
      audit/
      workers/
    alembic/
      versions/
    tests/
      unit/
      integration/
      contract/
  docs/
```

## 3) Initial Task List (Sprint 0-1)

### A. Contract/Schema Foundation
1. Freeze OpenAPI skeleton and error components
2. Add missing endpoint contracts:
   - `/api/orders/{id}/bulk-transition`
   - `/api/invoices/{id}/unlock`
3. Generate API client (frontend) from OpenAPI

### B. DB & Migration
1. Create/align status & enum columns per finalized docs
2. Add optimistic lock `version` columns (target tables)
3. Add indexes for transition-heavy queries
4. Add audit log schema and base writer utility

### C. Backend Core Logic
1. Implement transition service (line-first + user-triggered order bulk)
2. Implement cancel/reset synchronization rule:
   - line_status + invoice_line_status update together
3. Implement unlock policy:
   - finalized+locked only, admin only, reason required
4. Implement error code mapping (including `STATUS_NO_TARGET_LINES`)

### D. Frontend Core Screens
1. Orders list/detail with line filter by status
2. Bulk transition action panel (same-day repeated run allowed)
3. Invoice finalize/reset/unlock actions with reason inputs
4. Audit log viewer (CSV export)

### E. Quality & UAT Readiness
1. Contract tests against OpenAPI
2. Integration tests for boundary rules (cancel/reset/unlock)
3. Load test scripts (k6) using fixed UAT data profile
4. UAT execution evidence template rollout

## 4) Done Criteria (Implementation Ready)
- All required endpoints return standardized error schema
- Transition boundary rules pass integration tests
- UAT fixed thresholds are measurable in staging
- No unresolved mismatch between docs and OpenAPI
- Decision logs and spec index updated for every finalized change

## 5) Risks / Watchpoints
- Doc/OpenAPI drift during rapid edits
- Ambiguous field naming if API contracts are edited manually
- Missing audit fields in exceptional operations
- Performance regressions under 10 concurrent users + large line volume

## 6) Immediate Next Actions (This Week)
1. Lock OpenAPI endpoints and generate backend stubs
2. Implement transition service + test `STATUS_NO_TARGET_LINES`
3. Implement unlock endpoint with full audit payload
4. Run first staging load test with fixed UAT profile
