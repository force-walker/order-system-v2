# 02. Screens and Responsibilities (MVP)

Date: 2026-03-22
Status: Draft for implementation handoff

## Purpose
Define screen inventory and responsibilities for MVP, including key actions and navigation targets.

## Screen List

## S01. Order List / Search
- Primary users: order_entry, buyer, billing, admin
- Responsibility:
  - Search and filter orders
  - Check lifecycle status and drill down
- Key actions:
  - Filter by status/date/customer
  - Open order detail
- Main navigation:
  - -> S02 Order Entry / Edit
  - -> S03 Allocation Workbench
  - -> S05 Invoice Management

## S02. Order Entry / Edit
- Primary users: order_entry, admin
- Responsibility:
  - Create/update order header
  - Add/update/cancel order lines
  - Confirm/cancel order
- Key actions:
  - Save draft order
  - Confirm order (`new -> confirmed`)
  - Cancel line/order with reason
- Main navigation:
  - -> S01 Order List
  - -> S03 Allocation Workbench (after confirmed)

## S03. Allocation Workbench
- Primary users: buyer, admin
- Responsibility:
  - Run allocation process
  - Review suggested/final supplier allocations
  - Apply override and split
- Key actions:
  - Start allocation run
  - Override supplier/qty
  - Split allocation lines
  - Trigger transition `confirmed -> allocated`
- Main navigation:
  - -> S04 Purchase Result Entry
  - -> S01 Order List

## S04. Purchase Result Entry
- Primary users: buyer, admin
- Responsibility:
  - Register actual purchase outcomes
  - Handle shortage/substitution statuses
- Key actions:
  - Input purchased qty/cost/result status
  - Bulk upsert purchase results
  - Trigger transition `allocated -> purchased` and `purchased -> shipped`
- Main navigation:
  - -> S05 Invoice Management
  - -> S03 Allocation Workbench

## S05. Invoice Management (Generate / Finalize)
- Primary users: billing, admin
- Responsibility:
  - Generate invoice drafts
  - Validate and finalize invoices
  - Reset/unlock under policy
- Key actions:
  - Generate invoices
  - Edit invoice lines (billable qty/uom/price)
  - Finalize invoice (`shipped -> invoiced`)
  - Reset to draft / unlock with reason and role checks
- Main navigation:
  - -> S01 Order List
  - -> S06 Audit / Admin

## S06. Audit / Admin
- Primary users: admin (and limited viewers per policy)
- Responsibility:
  - Review critical operation audit trail
  - Validate operational/security events
- Key actions:
  - Search audit logs by entity/action/date/user
  - Review cancel/override/reset/unlock history
- Main navigation:
  - -> S01 Order List
  - -> S05 Invoice Management

---

## Lifecycle Coverage Matrix

- Order intake: S01/S02
- Allocation: S03
- Purchase result registration: S04
- Billing generation/finalization: S05
- Auditing/administration: S06

---

## Role-to-Screen Access (MVP)

- order_entry: S01, S02
- buyer: S01, S03, S04
- billing: S01, S05
- admin: S01-S06 all

(Exact endpoint-level permissions are defined in authz/API policy docs.)

---

## References
- `docs/architecture/03-api-catalog.md`
- `docs/architecture/05-authn-authz.md`
- `docs/architecture/02-status-model.md`
- `docs/rbac-draft.md`
