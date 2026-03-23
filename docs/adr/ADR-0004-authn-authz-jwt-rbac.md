# ADR-0004: Authentication and Authorization Model

- Status: Accepted
- Date: 2026-03-22

## Context
Need secure, simple MVP auth model with clear role boundaries.

## Decision
- Authentication: JWT (access + refresh)
- Authorization: RBAC (`admin`, `order_entry`, `buyer`, `billing`)
- Sensitive operations require reason code + audit logging.

## Consequences
- Pros: standard, implementable quickly, clear endpoint protection model.
- Cons: token lifecycle and revocation operations required.

## References
- `docs/architecture/05-authn-authz.md`
- `docs/api-authorization-spec-draft.md`
