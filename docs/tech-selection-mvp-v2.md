# Tech Selection (MVP v2)

Date: 2026-03-17

## Decision Table

- Backend API
  - Option: FastAPI + SQLAlchemy + Alembic
  - Decision: Adopted
  - Why: Existing repo stack, fast delivery, typed API schema compatibility

- Database
  - Option: PostgreSQL
  - Decision: Adopted
  - Why: Transactional consistency, enum/constraint support, mature ops

- Batch/Async
  - Option: In-process/background job for MVP (future: Redis/Celery)
  - Decision: Adopted (MVP)
  - Why: Lower operational complexity now, extension path kept

- API Spec
  - Option: OpenAPI 3.0 skeleton + incremental expansion
  - Decision: Adopted
  - Why: Contract-first collaboration and testability

- AuthN/AuthZ
  - Option: JWT (access/refresh) + RBAC
  - Decision: Adopted
  - Why: Matches role model and endpoint-level control needs

- Observability
  - Option: Structured logs + metrics + alert rules
  - Decision: Adopted
  - Why: Supports SLO monitoring and incident response

- Migration
  - Option: Alembic incremental revisions
  - Decision: Adopted
  - Why: Safe schema evolution and rollback traceability

## Deferred / vNext
- External queue (Redis/Celery) hard adoption
- Advanced BI pipeline
- Accounting scope (`paid` status)
- Fine-grained post-unlock editable-field restrictions

## Non-functional alignment
- API P95 <= 1.5s
- Grid initial response P95 <= 2.0s
- Allocation batch 5,000 lines <= 5 min
- Availability 99.5% monthly
- RPO <= 1h / RTO <= 4h
