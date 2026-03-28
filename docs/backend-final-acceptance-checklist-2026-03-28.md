# Backend Final Acceptance Checklist (2026-03-28)

Status: Ready for handoff to Frontend (Mockup Resume)
Scope: DB + API contract alignment against `docs/architecture/04-db-core-tables.md`

## 1) Table-by-table requirement alignment

- [x] products
  - [x] required columns present
  - [x] unique constraint on `sku`
  - [x] API contract and tests aligned
  - PR refs: #16, #18, #28

- [x] customers
  - [x] `customer_code` naming aligned
  - [x] unique constraint on `customer_code`
  - [x] API/tests/seed aligned
  - PR refs: #35

- [x] orders
  - [x] `order_no` system-generated (no manual input)
  - [x] `created_by` / `updated_by` added
  - [x] status transitions validated
  - PR refs: #34, #41

- [x] order_items
  - [x] `order_uom_type`, `estimated_weight_kg`, `actual_weight_kg` added
  - [x] price-by-pricing-basis DB check implemented
  - PR refs: #37

- [x] supplier_allocations
  - [x] suggested/final/split linkage fields added
  - [x] self-FK `parent_allocation_id` added
  - [x] `final_qty >= 0` aligned
  - PR refs: #38, #43

- [x] purchase_results
  - [x] supplier/weight/cost/shortage/recorded fields added
  - [x] cardinality aligned to 1-N (unique removed)
  - [x] `result_status` enum constrained
  - PR refs: #39, #43

- [x] invoices
  - [x] core columns and constraints aligned
  - PR refs: #16, #18

- [x] invoice_items
  - [x] table/model/constraints/indexes implemented
  - PR refs: #40

- [x] batch_jobs
  - [x] integrity constraints + operational indexes in place
  - PR refs: #20, #26

- [x] audit_logs
  - [x] `before_json`, `after_json`, `trace_id`, `request_id`, `job_id` implemented
  - [x] API serialization aligned
  - PR refs: #42

## 2) API behavior policy checks

- [x] 409/422 classification fixed and tested
  - 422: input/validation
  - 409: state conflict
  - PR refs: #15, #16, #17, #21, #43

- [x] OpenAPI alignment
  - runtime `/openapi.json` synchronized to docs
  - contract tests added
  - PR refs: #14, #16, #22

- [x] Regression matrix tests
  - success + 409/422/404 representative paths covered
  - PR refs: #25, #28, #43

## 3) Migration & quality gates

- [x] migrations verified on clean DB repeatedly
- [x] latest migration head: `2026032809`
- [x] lint/test gate passing in CI for merged PRs

## 4) Frontend handoff readiness

- [x] API freeze document exists
  - `docs/frontend-api-contract-freeze-2026-03.md`
- [x] mockup quickstart exists
  - `docs/frontend-mockup-dev-quickstart.md`
- [x] seed script exists
  - `backend/scripts/seed_frontend_mock_data.py`

## 5) Acceptance decision

Decision: **Backend acceptance complete for current requirement set.**

Recommended next phase: **Resume Frontend implementation/mockup.**

Notes:
- If new requirements emerge, continue with 1-feature-1-PR and keep OpenAPI/test parity.
