# 05. Authentication / Authorization (MVP)

Date: 2026-03-21
Status: Draft for implementation handoff

## Purpose
Define the MVP authentication and authorization model aligned with existing requirements and API catalog.

## 1) Authentication (AuthN)

## Scheme
- **JWT-based auth**
  - Access Token (short-lived)
  - Refresh Token (longer-lived)
- Transport: HTTPS only
- Token location:
  - Access token: `Authorization: Bearer <token>`
  - Refresh token: secure storage (httpOnly cookie or secure server-side handling policy)

## Recommended TTL (MVP)
- Access token: 15 minutes
- Refresh token: 7 days

## Session policy
- Re-login required after refresh expiry
- Logout invalidates refresh token server-side (token revocation list/table)

## Required claims (access token)
- `sub` (user id)
- `role` (primary role)
- `scopes` (optional, endpoint-level granularity)
- `iat`, `exp`
- `jti` (token id, for revocation/audit)

---

## 2) Authorization (AuthZ)

## Model
- **RBAC** as baseline
- Role checks at API layer (dependency/middleware)
- Fine-grained checks in service layer for business operations

## MVP roles
- `admin`
- `order_entry`
- `buyer`
- `billing`

## High-level responsibility mapping
- order_entry:
  - order create/update/confirm, line edit/cancel
- buyer:
  - allocation run/review/override
  - purchase result input
  - transitions up to shipped
- billing:
  - invoice generate/edit/finalize/reset-to-draft (as policy allows)
  - shipped->invoiced transition
- admin:
  - full access including unlock and emergency operations

---

## 3) Endpoint Protection Rules

## Always protected (auth required)
- all `/api/v1/*` business endpoints

## Public/minimal
- `/api/v1/health` may be public (or protected internal endpoint)
- `/api/v1/metrics` internal only (network-level + auth)

## Policy checks
- 401: missing/invalid token
- 403: authenticated but not authorized

---

## 4) Sensitive Operations Policy

The following operations require explicit reason code and audit logging:
- cancel
- override
- reset-to-draft
- unlock
- status_change (critical transitions)

Additional restrictions:
- `unlock` is admin-only
- invoice finalize/reset/unlock must enforce state preconditions

---

## 5) Security Controls (MVP minimum)

- Password hashing: Argon2 or bcrypt
- Brute-force mitigation:
  - login rate limit
  - temporary lock/backoff after repeated failures
- Token signing key rotation plan (manual rotation acceptable in MVP)
- CORS restricted to frontend origin(s)
- CSRF considerations if cookie-based refresh token is used

---

## 6) Audit & Traceability (Auth-related)

Track the following events:
- login success/failure
- token refresh success/failure
- logout
- forbidden access attempts (403)

Required fields in auth/security logs:
- `user_id` (if known)
- `trace_id`, `request_id`
- endpoint
- outcome (success/failure)
- reason/error code
- timestamp

---

## 7) Implementation Notes

- Keep role enum centrally defined and reused across API/service checks.
- Avoid role logic duplication in controllers.
- Map roles/scopes to OpenAPI security docs for consistency.

---

## 8) References
- `docs/rbac-draft.md`
- `docs/api-authorization-spec-draft.md`
- `docs/architecture/03-api-catalog.md`
- `docs/architecture/07-observability.md`
