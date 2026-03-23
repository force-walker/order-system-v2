# Architecture Index (MVP v2)

Status: Completed baseline
Last updated: 2026-03-22

## Core Architecture Documents

1. [01-system-context.md](./01-system-context.md)
   - System context, component boundaries, external integration minimum set

2. [02-screens-and-responsibilities.md](./02-screens-and-responsibilities.md)
   - Screen inventory, role ownership, key actions, navigation

3. [02-status-model.md](./02-status-model.md)
   - Fixed status model translated into implementation rules

4. [03-api-catalog.md](./03-api-catalog.md)
   - API list mapped to screen responsibilities

5. [04-db-core-tables.md](./04-db-core-tables.md)
   - Core tables, keys, constraints, DB/app responsibility boundaries

6. [05-authn-authz.md](./05-authn-authz.md)
   - JWT + RBAC model and sensitive operation controls

7. [06-error-model.md](./06-error-model.md)
   - Unified error response format and HTTP/code mapping

8. [07-observability.md](./07-observability.md)
   - Structured logs, minimum metrics, alerts, dashboards

9. [99-open-questions.md](./99-open-questions.md)
   - Open questions and assumptions for handoff clarity

## ADRs

- [ADR-0001-mvp-architecture-baseline.md](../adr/ADR-0001-mvp-architecture-baseline.md)
- [ADR-0002-status-transition-policy.md](../adr/ADR-0002-status-transition-policy.md)
- [ADR-0003-dual-uom-catch-weight.md](../adr/ADR-0003-dual-uom-catch-weight.md)
- [ADR-0004-authn-authz-jwt-rbac.md](../adr/ADR-0004-authn-authz-jwt-rbac.md)
- [ADR-0005-unified-error-model.md](../adr/ADR-0005-unified-error-model.md)
- [ADR-0006-minimum-observability-baseline.md](../adr/ADR-0006-minimum-observability-baseline.md)

## Notes
- This package is intended to be implementation-ready for Infra/DevOps and Backend planning.
- Requirement-level decisions remain in requirements documents; architecture docs focus on implementation realization.
