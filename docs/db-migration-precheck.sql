-- DB Migration Precheck for Alembic upgrade to head (MVP v2 alignment)
-- Target revisions: 2026031701 -> 2026031704

-- 1) Existing enums and labels
SELECT t.typname AS enum_name, e.enumlabel
FROM pg_type t
JOIN pg_enum e ON t.oid = e.enumtypid
ORDER BY t.typname, e.enumsortorder;

-- 2) Columns depending on target enums
SELECT n.nspname, c.relname, a.attname, t.typname
FROM pg_attribute a
JOIN pg_class c ON a.attrelid = c.oid
JOIN pg_type t ON a.atttypid = t.oid
JOIN pg_namespace n ON c.relnamespace = n.oid
WHERE t.typname IN ('pricingbasis','orderstatus','linestatus','invoicestatus')
  AND a.attnum > 0
  AND NOT a.attisdropped
ORDER BY t.typname, c.relname, a.attname;

-- 3) Data distribution checks (before mapping)
SELECT status::text, COUNT(*) FROM orders GROUP BY status::text ORDER BY 1;
SELECT line_status::text, COUNT(*) FROM order_items GROUP BY line_status::text ORDER BY 1;
SELECT pricing_basis_default::text, COUNT(*) FROM products GROUP BY pricing_basis_default::text ORDER BY 1;
SELECT pricing_basis::text, COUNT(*) FROM order_items GROUP BY pricing_basis::text ORDER BY 1;
SELECT status::text, COUNT(*) FROM invoices GROUP BY status::text ORDER BY 1;

-- 4) Potential check-constraint violations after migration
-- pricing_basis rule
SELECT id, pricing_basis::text, unit_price_uom_count, unit_price_uom_kg
FROM order_items
WHERE NOT (
  (pricing_basis::text='uom_count' AND unit_price_uom_count IS NOT NULL)
  OR
  (pricing_basis::text='uom_kg' AND unit_price_uom_kg IS NOT NULL)
);

-- 5) Existing objects that may conflict with adds
SELECT column_name
FROM information_schema.columns
WHERE table_name='orders' AND column_name='delivery_date';

SELECT column_name
FROM information_schema.columns
WHERE table_name='purchase_results'
  AND column_name IN ('supplier_id','final_unit_cost','shortage_qty','shortage_policy','invoiceable_flag','updated_at');

SELECT column_name
FROM information_schema.columns
WHERE table_name='invoice_items'
  AND column_name IN ('billable_qty','billable_uom','invoice_line_status','sales_unit_price','line_amount','unit_cost_basis','created_at','updated_at');

SELECT tablename, indexname
FROM pg_indexes
WHERE indexname IN (
  'ix_invoices_status',
  'ix_invoice_items_order_item_id',
  'ix_audit_entity_changed_at',
  'ix_audit_changed_by_changed_at'
)
ORDER BY indexname;
