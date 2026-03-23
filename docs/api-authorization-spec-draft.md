# API Authorization Spec Draft (MVP)

Updated: 2026-03-10

## Roles
- `admin`
- `order_entry`
- `buyer`
- `supplier`
- `customer`

---

## Authorization model

- Endpoint access is controlled by role + resource scope.
- Write operations require authenticated user id.
- Critical operations require `reason_code` and are always audit-logged.

Scope rules:
- `supplier`: only allocations/purchase-results assigned to own supplier id
- `customer`: only own orders for delivery confirmation endpoints
- `order_entry`/`buyer`: internal scope (tenant-level)
- `admin`: unrestricted within tenant

---

## Endpoint-level policy matrix

## Products
- `POST /api/products`
  - Roles: `admin`

## Orders
- `POST /api/orders`
  - Roles: `admin`, `order_entry`
- `POST /api/orders/{id}/confirm`
  - Roles: `admin`, `order_entry`, `buyer` (delegated mode)

## Allocations
- `POST /api/allocations/run-auto`
  - Roles: `admin`, `buyer`
- `PATCH /api/allocations/{id}/override`
  - Roles: `admin`, `buyer`
  - `override_reason_code` is optional
- `POST /api/allocations/{id}/split-line`
  - Roles: `admin`, `buyer`
  - `override_reason_code` is optional
- `POST /api/allocations/confirm`
  - Roles: `admin`, `buyer`
  - Validation: split-group integrity checks

## Purchase Results
- `POST /api/purchase-results`
  - Roles: `admin`, `buyer`, `supplier` (own assigned lines only)
- `PATCH /api/purchase-results/{id}`
  - Roles: `admin`, `buyer`, `supplier` (own lines, limited fields)
- `PATCH /api/purchase-results/{id}/final-cost`
  - Roles: `admin`, `buyer`, `supplier` (own lines only)
  - Supplier update is allowed with mandatory audit log; buyer/admin performs pre-invoice final review

## Delivery Confirmation
- `POST /api/deliveries/{order_id}/confirm-receipt`
  - Roles: `admin`, `buyer`, `customer` (own order only), `order_entry` (fallback)

## Invoices
- `POST /api/invoices`
  - Roles: `admin`, `order_entry`
- `POST /api/invoices/{id}/finalize`
  - Roles: `admin`, `order_entry`
  - Hard-stop checks:
    - catch-weight has `actual_weight_kg`
    - required pricing present
    - no negative totals

## Cancellation / Status
- `POST /api/orders/{id}/cancel`
  - Roles:
    - `new`, `confirmed`: `admin`, `order_entry`, `buyer`
    - `allocated`, `purchased`, `shipped`: `admin`, `buyer`
    - `invoiced`: blocked by default in MVP (admin override policy optional)
  - Required: `cancel_reason_code`

## Audit Logs
- `GET /api/audit-logs`
  - Roles: `admin`
- `GET /api/audit-logs/me`
  - Roles: `order_entry`, `buyer` (own scope)

---

## Field-level restrictions

- `supplier` cannot edit:
  - allocation supplier assignment
  - invoice fields
  - final status transitions
- `customer` can only submit receipt confirmation and view own delivery status
- `buyer` cannot finalize invoice by default

---

## Required audit events

Trigger audit event on:
- allocation override
- split-line
- cancel
- status transitions (except automated no-op)
- final-cost updates
- invoice finalize

Minimum payload:
- `entity_type`, `entity_id`
- `action`
- `before_json`, `after_json`
- `reason_code` (when required)
- `changed_by`, `changed_at`

---

## Error semantics (authorization)
- `401 Unauthorized`: missing/invalid auth
- `403 Forbidden`: role not allowed or out-of-scope resource
- `409 Conflict`: state transition rule violation
- `422 Unprocessable Entity`: validation failed
