# 04. DB Core Tables (MVP v2)

Date: 2026-03-21
Status: Draft for implementation handoff

## Purpose
Finalize core table definitions, keys, and constraint boundaries for MVP implementation.

## Design Principles
- PostgreSQL as source of truth.
- Use hard DB constraints for identity/integrity basics.
- Keep workflow-level rules in application service layer.
- Dual-UOM and catch-weight are first-class data model concerns.

---

## 1) Core Tables

### 1. products
Role: Product master and UOM/pricing defaults

Key columns:
- `id` (PK)
- `sku` (UNIQUE)
- `name`
- `order_uom`, `purchase_uom`, `invoice_uom`
- `is_catch_weight` (bool)
- `pricing_basis_default` (`uom_count|uom_kg`)
- `active`

Constraints:
- `sku` unique

Indexes:
- `idx_products_sku`
- `idx_products_active`

### 2. customers
Role: Customer master

Key columns:
- `id` (PK)
- `customer_code` (UNIQUE)
- `name`
- `active`

Constraints:
- `customer_code` unique

### 3. orders
Role: Order header

Key columns:
- `id` (PK)
- `order_no` (UNIQUE)
- `customer_id` (FK -> customers.id)
- `order_datetime`
- `delivery_date`
- `status` (`new|confirmed|allocated|purchased|shipped|invoiced|cancelled`)
- `created_by`, `updated_by`

Constraints:
- `order_no` unique
- `customer_id` FK required

Indexes:
- `idx_orders_status`
- `idx_orders_order_datetime`
- `idx_orders_customer_id`

### 4. order_items
Role: Order line details with dual-UOM pricing

Key columns:
- `id` (PK)
- `order_id` (FK -> orders.id)
- `product_id` (FK -> products.id)
- `ordered_qty` (numeric, > 0)
- `order_uom_type` (`uom_count|uom_kg`)
- `estimated_weight_kg`, `actual_weight_kg`
- `pricing_basis` (`uom_count|uom_kg`)
- `unit_price_uom_count`, `unit_price_uom_kg`
- `line_status` (`open|allocated|purchased|shipped|invoiced|cancelled`)

Constraints:
- `ordered_qty > 0`
- price-by-basis check:
  - if `pricing_basis=uom_count` then `unit_price_uom_count` is required
  - if `pricing_basis=uom_kg` then `unit_price_uom_kg` is required

Indexes:
- `idx_order_items_order_id`
- `idx_order_items_product_id`
- `idx_order_items_line_status`

### 5. supplier_allocations
Role: Auto allocation + manual override/split tracking

Key columns:
- `id` (PK)
- `order_item_id` (FK -> order_items.id)
- `suggested_supplier_id`, `final_supplier_id`
- `suggested_qty`, `final_qty`
- `is_manual_override`
- `override_reason_code`
- `target_price`
- `stockout_policy` (`backorder|substitute|cancel|split`)
- `split_group_id`, `parent_allocation_id`, `is_split_child`

Constraints:
- self FK on `parent_allocation_id`
- `final_qty >= 0` (if present)

Indexes:
- `idx_allocations_order_item_id`
- `idx_allocations_final_supplier_id`
- `idx_allocations_manual_override`
- `idx_allocations_split_group_id`
- `idx_allocations_parent_allocation_id`
- `idx_allocations_is_split_child`

### 6. purchase_results
Role: Record actual purchase outcomes

Key columns:
- `id` (PK)
- `allocation_id` (FK -> supplier_allocations.id)
- `supplier_id`
- `purchased_qty` (> 0)
- `actual_weight_kg`
- `unit_cost`, `final_unit_cost`
- `result_status` (`not_filled|filled|partially_filled|substituted`)
- `shortage_qty`, `shortage_policy`
- `invoiceable_flag`
- `recorded_by`, `recorded_at`

Constraints:
- `purchased_qty > 0`

Indexes:
- `idx_purchase_results_allocation_id`
- `idx_purchase_results_supplier_id`
- `idx_purchase_results_result_status`

### 7. invoices
Role: Invoice header

Key columns:
- `id` (PK)
- `invoice_no` (UNIQUE)
- `customer_id` (FK -> customers.id)
- `invoice_date`, `delivery_date`
- `subtotal`, `tax_total`, `grand_total`
- `status` (`draft|finalized|sent|cancelled`)

Constraints:
- `invoice_no` unique

Indexes:
- `idx_invoices_customer_id`
- `idx_invoices_invoice_date`
- `idx_invoices_status`

### 8. invoice_items
Role: Invoice lines derived from order items (split billing supported)

Key columns:
- `id` (PK)
- `invoice_id` (FK -> invoices.id)
- `order_item_id` (FK -> order_items.id)
- `billable_qty`, `billable_uom`
- `invoice_line_status` (`uninvoiced|partially_invoiced|invoiced|cancelled`)
- `sales_unit_price`
- `unit_cost_basis`
- `line_amount`, `tax_amount`

Constraints:
- `sales_unit_price >= 0`

Indexes:
- `idx_invoice_items_invoice_id`
- `idx_invoice_items_order_item_id`

### 9. audit_logs
Role: Critical action traceability

Key columns:
- `id` (PK)
- `entity_type`, `entity_id`
- `action`
- `before_json`, `after_json`
- `reason_code`
- `changed_by`, `changed_at`
- correlation: `trace_id`, `request_id`, `job_id` (implemented)

Indexes:
- `idx_audit_entity`
- `idx_audit_changed_at`
- `ix_audit_entity_changed_at`
- `ix_audit_changed_by_changed_at`

---

## 2) Relation Summary
- `customers 1 - N orders`
- `orders 1 - N order_items`
- `products 1 - N order_items`
- `order_items 1 - N supplier_allocations`
- `supplier_allocations 1 - N purchase_results`
- `invoices 1 - N invoice_items`
- `order_items 1 - N invoice_items`

---

## 3) DB vs Application Responsibility Boundary

## DB handles
- identity and referential integrity (PK/FK/UNIQUE)
- numeric/check constraints
- enum domain safety

### Implemented integrity constraints (runtime)
- `order_items.ordered_qty > 0`
- `order_items.order_uom_type` added (`uom_count|uom_kg`)
- `order_items.estimated_weight_kg`, `order_items.actual_weight_kg` added
- `order_items` price required by pricing basis (`uom_count => unit_price_uom_count`, `uom_kg => unit_price_uom_kg`)
- `supplier_allocations.final_qty IS NULL OR final_qty >= 0`
- `supplier_allocations.suggested_supplier_id`, `suggested_qty`, `target_price` added
- `supplier_allocations.parent_allocation_id` (self FK), `is_split_child` added
- `supplier_allocations.suggested_qty IS NULL OR suggested_qty > 0`
- `purchase_results.purchased_qty > 0`
- `purchase_results.supplier_id`, `actual_weight_kg`, `unit_cost`, `final_unit_cost`, `shortage_qty`, `shortage_policy`, `recorded_by` added
- `purchase_results.actual_weight_kg > 0` when provided
- `purchase_results.unit_cost/final_unit_cost/shortage_qty >= 0` when provided
- `purchase_results.result_status` constrained by enum (`not_filled|filled|partially_filled|substituted`)
- `invoice_items` table implemented (`invoice_id`, `order_item_id`, `billable_qty/uom`, status, pricing/tax fields)
- `invoice_items.sales_unit_price >= 0`
- `invoices.due_date IS NULL OR due_date >= invoice_date`
- `invoices.subtotal/tax_total/grand_total >= 0`
- `batch_jobs` counters non-negative, `max_retries >= 1`, `retry_count <= max_retries`

### Implemented minimal performance indexes (runtime)
- `ix_batch_jobs_type_business_date_status` on `(job_type, business_date, status)`
- `ix_audit_logs_entity_type_entity_id_changed_at` on `(entity_type, entity_id, changed_at)`
- `ix_audit_logs_changed_by_changed_at` on `(changed_by, changed_at)`

### 409/422 alignment guideline
- DB uniqueness/FK/check violations should map to:
  - `409 Conflict` for uniqueness/state-conflict semantics
  - `422 Unprocessable Entity` for payload validation semantics
- Prefer pre-check in API where feasible, with DB constraints as final guardrail.

## Application handles
- status transition eligibility and role checks
- catch-weight finalize-time validations
- multi-entity workflow invariants
- idempotent bulk execution semantics

---

## 4) Implementation Notes
- Keep quantity/weight/amount columns as `numeric` (not float).
- Keep invoice amount/tax calculations server-authoritative.
- Add missing columns/indexes incrementally via Alembic revisions.
- Verify migration safety with `docs/db-migration-precheck.sql` before upgrade.

---

## 5) References
- `docs/architecture/02-status-model.md`
- `docs/db-dual-uom-draft.md`
- `backend/alembic/versions/2026031701_core_v2_alignment.py`
- `backend/alembic/versions/2026031702_allocation_v2_alignment.py`
- `backend/alembic/versions/2026031703_invoice_v2_alignment.py`
- `backend/alembic/versions/2026031704_audit_v2_alignment.py`
