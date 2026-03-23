# DB Draft: Dual-UOM + Catch-Weight Support

## Goal
Support operations where orders are entered in one unit (e.g., piece) while purchasing/invoicing are finalized in another (e.g., kg actual weight).

---

## Core Concepts

- **Order UOM**: Unit used by order-entry staff (`piece`, `box`, etc.)
- **Purchase UOM**: Unit used for supplier purchase (`kg`, `case`, etc.)
- **Invoice UOM / Basis**: Unit and logic used for billing customer (`uom_kg` for catch-weight)
- **Catch-weight item**: Item sold by actual measured weight at fulfillment time

---

## Proposed Tables / Key Columns

## 1) `products`
Master rules per item.

- `id` (PK)
- `sku` (unique)
- `name`
- `order_uom` (varchar)
- `purchase_uom` (varchar)
- `invoice_uom` (varchar)
- `is_catch_weight` (boolean, default false)
- `weight_capture_required` (boolean, default false)
- `pricing_basis_default` (`uom_count` | `uom_kg`)  ※`product_id`で固定
- `rounding_weight_scale` (int, e.g., 3)
- `rounding_amount_scale` (int, e.g., 0 for JPY)
- `active` (boolean)
- `created_at`, `updated_at`

Indexes:
- `idx_products_sku`
- `idx_products_active`

## 2) `orders`
Order header.

- `id` (PK)
- `order_no` (unique)
- `customer_id` (FK)
- `customer_name` (snapshot)
- `customer_address` (snapshot)
- `billing_customer_id` (FK)
- `billing_address` (snapshot)
- `order_datetime`
- `delivery_date` (date, default: order date + 1 day, editable)
- `delivery_type` (`delivery` | `pickup`)
- `delivery_address_snapshot` (text/json)
- `order_source` (nullable)
- `cutoff_datetime` (timestamp)
- `payment_method` (nullable)
- `payment_status` (nullable)
- `status` (`new` | `confirmed` | `allocated` | `purchased` | `shipped` | `invoiced` | `cancelled`)
- `note` (nullable)
- `created_by`, `created_at`, `updated_by`, `updated_at`

Indexes:
- `idx_orders_customer_id`
- `idx_orders_status`
- `idx_orders_order_datetime`

## 3) `order_items`
Line-level unit/weight/price details.

- `id` (PK)
- `order_id` (FK)
- `product_id` (FK)
- `ordered_qty` (numeric(12,2))
- `order_uom_type` (`uom_count` | `uom_kg`, product masterから自動反映)
- `estimated_weight_kg` (numeric(12,3), nullable)
- `actual_weight_kg` (numeric(12,3), nullable)  ※受注時は不要、仕入結果登録で確定
- `pricing_basis` (`uom_count` | `uom_kg`)  ※`product_id`で自動決定（手入力不可）
- `unit_price_uom_count` (numeric(12,2), nullable)
- `unit_price_uom_kg` (numeric(12,2), nullable)
- `line_subtotal` (numeric(12,2), nullable or computed)
- `line_tax` (numeric(12,2), nullable or computed)
- `line_total` (numeric(12,2), nullable or computed)
- `line_status` (`open` | `allocated` | `purchased` | `shipped` | `invoiced` | `cancelled`)
- `created_at`, `updated_at`

Validation rules:
- `ordered_qty > 0`
- `product_id`ごとに`is_catch_weight`と`order_uom_type`は一意（混在禁止）
- If `pricing_basis = uom_kg` then `unit_price_uom_kg` required
- If `pricing_basis = uom_count` then `unit_price_uom_count` required
- tax関連項目は請求時に扱う（受注時は不要）

Indexes:
- `idx_order_items_order_id`
- `idx_order_items_product_id`
- `idx_order_items_line_status`

## 4) `supplier_allocations`
Auto-suggest + manual override trail.

- `id` (PK)
- `order_item_id` (FK)
- `suggested_supplier_id` (FK)
- `final_supplier_id` (FK)
- `suggested_qty` (numeric(12,3))
- `suggested_uom` (varchar)
- `final_qty` (numeric(12,3))
- `final_uom` (varchar)
- `is_manual_override` (boolean, default false)
- `override_reason_code` (varchar, nullable)
- `override_note` (text, nullable)
- `overridden_by` (FK user, nullable)
- `overridden_at` (timestamp, nullable)
- `target_price` (numeric(12,2), nullable)  ← 希望価格
- `stockout_policy` (`backorder` | `substitute` | `cancel` | `split`, nullable)
- `comment` (text, nullable)
- `split_group_id` (varchar, nullable)
- `parent_allocation_id` (self FK, nullable)
- `is_split_child` (boolean, default false)
- `created_at`, `updated_at`

Indexes:
- `idx_allocations_order_item_id`
- `idx_allocations_final_supplier_id`
- `idx_allocations_manual_override`
- `idx_allocations_split_group_id`
- `idx_allocations_parent_allocation_id`
- `idx_allocations_is_split_child`

## 5) `purchase_results`
Record actual buying outcome.

- `id` (PK)
- `allocation_id` (FK)
- `supplier_id` (FK, default from allocation final supplier, editable at registration)
- `purchased_qty` (numeric(12,3))
- `purchased_uom` (varchar)
- `actual_weight_kg` (numeric(12,3), nullable)  ※受注時は不要、仕入結果登録で確定
- `unit_cost` (numeric(12,2), nullable)  ※初期記録
- `final_unit_cost` (numeric(12,2), nullable)  ※最終仕入れ単価（確定値）
- `transport_cost` (numeric(12,2), nullable)
- `currency` (varchar(3), default `JPY`)  ※仕入通貨
- `is_final` (boolean, default false)
- `result_status` (`not_filled` | `filled` | `partially_filled` | `substituted`)
- `shortage_qty` (numeric(12,3), nullable)
- `shortage_policy` (`backorder` | `cancel` | `substitute` | `split`, nullable)
- `shortage_reason_code` (`stockout` | `quality_issue` | `delivery_delay` | `supplier_reject` | `manual_adjustment`, nullable)
- `shortage_note` (nullable; required if `shortage_reason_code=manual_adjustment`)
- `final_billable_qty` (numeric(12,3), nullable)
- `final_billable_uom` (varchar, nullable)
- `invoiceable_flag` (boolean, default true)
- `invoice_block_reason` (nullable)
- `recorded_by` (FK user)
- `recorded_at` (timestamp)
- `comment` (nullable)

Indexes:
- `idx_purchase_results_allocation_id`
- `idx_purchase_results_supplier_id`
- `idx_purchase_results_result_status`

Operational note:
- Purchase result entry screen should display supplier and support sorting/filtering by supplier to speed up data entry.

## 6) `invoices` / `invoice_items`
Billing output.

`invoices`:
- `currency` (varchar(3), default `HKD`)  ※販売通貨
- `id` (PK)
- `invoice_no` (unique)
- `customer_id` (FK)
- `invoice_customer_name` (snapshot)
- `invoice_customer_address` (snapshot)
- `invoice_date`
- `delivery_date` (date, single date per invoice)
- `payment_terms` (nullable)
- `due_date` (nullable)
- `subtotal`, `tax_total`, `grand_total`
- `tax_rate` (nullable)
- `status` (`draft` | `finalized` | `sent` | `cancelled`)
- `created_by`, `created_at`, `updated_at`

`invoice_items`:
- `id` (PK)
- `invoice_id` (FK)
- `order_item_id` (FK)
- `description`
- `qty_display` (numeric)
- `uom_display` (varchar)
- `weight_kg` (nullable)
- `billable_qty` (numeric(12,3), nullable)
- `billable_uom` (varchar, nullable)
- `invoice_line_status` (`uninvoiced` | `partially_invoiced` | `invoiced` | `cancelled`)
- `sales_unit_price` (numeric(12,2))  ※販売単価
- `unit_cost_basis` (numeric(12,2))  ※粗利計算用原価（split時は加重平均）
- `gross_margin_rate` (numeric(8,4), nullable)  ※内部管理用（帳票非表示）
- `amount`
- `line_amount` (numeric(12,2), nullable)
- `discount` (numeric(12,2), nullable)
- `tax_code`, `tax_amount`, `line_tax_amount`

## 7) `audit_logs`
Required for critical/no-error operations.

- `id` (PK)
- `entity_type` (e.g., `allocation`, `order_item`, `invoice`)
- `entity_id`
- `action` (`create` | `update` | `status_change` | `override`)
- `before_json` (jsonb)
- `after_json` (jsonb)
- `reason_code` (nullable)
- `changed_by`
- `changed_at`

Indexes:
- `idx_audit_entity`
- `idx_audit_changed_at`

---

## Notes for MVP
- Keep all quantity/weight fields as `numeric`, not float.
- Keep invoice totals server-side authoritative.
- Do not allow invoice finalization if catch-weight item is missing `actual_weight_kg`.
- Keep a cutoff batch id (future table `operation_batches`) for nightly workflow traceability.
