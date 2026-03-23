# Non-Functional Requirements Draft (MVP)

Updated: 2026-03-10

## Goal
Define quality and operational constraints required for safe daily operation of the order system.

---

## 1) Performance / Throughput

### Peak-time assumption
- Order input cutoff around 01:00
- Allocation + purchasing preparation must finish within ~1 hour

### MVP targets
- Allocation run (`confirmed` lines):
  - Target: up to 5,000 lines processed within 5 minutes
- Allocation review grid load:
  - First view response: within 2 seconds (P95) for filtered view
- Invoice generation:
  - 1 invoice creation: within 1 second (P95)
  - 1,000 invoices batch: within 15 minutes

---

## 2) Availability / Reliability

- Service availability target: 99.5% monthly (MVP)
- Planned maintenance window: outside operation peak (default 03:00–05:00)
- On failure:
  - no silent data loss
  - recover from latest backup + audit trail

---

## 3) Data Integrity / Consistency

- Quantity/weight/amount fields must use `numeric/decimal` (not float)
- Server-side authoritative calculation for tax/totals
- Transactional write for critical workflows:
  - order creation (header + lines)
  - allocation split/override
  - invoice finalize
- Referential integrity with FK constraints

---

## 4) Security / Access Control

- Role-based access control (RBAC)
  - Order Entry / Buyer / Billing / Admin
- Principle of least privilege
- Sensitive actions require explicit reason code:
  - cancel
  - override
  - reopen-like backward transitions
- API authentication required (MVP can start with internal token + HTTPS)

---

## 5) Audit / Traceability

- All critical edits are audit-logged:
  - who / when / before / after / why
- Audit retention:
  - minimum 13 months (recommended)
- Exportable audit log for incident review

---

## 6) Backup / Recovery

- Database backup frequency:
  - daily full backup
  - hourly incremental (recommended)
- Recovery targets:
  - RPO: <= 1 hour
  - RTO: <= 4 hours
- Quarterly restore drill (recommended)

---

## 7) Observability / Operations

- Mandatory operational logs:
  - API request logs (with correlation id)
  - job logs (allocation/invoice batch)
  - error logs
- Metrics:
  - API latency/error rate
  - allocation run duration
  - invoice batch duration
- Alert examples:
  - allocation run failure
  - invoice finalization hard-stop spike
  - DB connection saturation

---

## 8) Usability (Operational)

- Unified grid behavior across By Supplier / By Customer / By Product
- Bulk operations for common tasks (supplier set, filter, export)
- Conflict/warning panel visible before confirm
- Input validation errors must be field-specific and actionable

---

## 9) Compliance / Data Handling (MVP baseline)

- Customer personal data should be minimized in logs
- Mask sensitive fields when exported externally
- Access to production data restricted by role

---

## 10) Future-readiness

- Prepare extension points for:
  - `paid` status + accounting integration
  - supervisor approval workflow
  - external supplier API integration
  - BI/reporting pipeline
