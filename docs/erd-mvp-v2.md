# ERD (MVP v2, Dual-UOM)

Date: 2026-03-17

```mermaid
erDiagram
  PRODUCTS ||--o{ ORDER_ITEMS : referenced_by
  CUSTOMERS ||--o{ ORDERS : places
  ORDERS ||--o{ ORDER_ITEMS : has

  ORDER_ITEMS ||--o{ SUPPLIER_ALLOCATIONS : allocated_into
  SUPPLIER_ALLOCATIONS ||--o{ PURCHASE_RESULTS : results

  INVOICES ||--o{ INVOICE_ITEMS : has
  ORDER_ITEMS ||--o{ INVOICE_ITEMS : billed_from

  PRODUCTS {
    bigint id PK
    string sku UK
    string name
    string order_uom
    string purchase_uom
    string invoice_uom
    boolean is_catch_weight
    enum pricing_basis_default "uom_count|uom_kg"
    boolean active
  }

  CUSTOMERS {
    bigint id PK
    string customer_code UK
    string name
    boolean active
  }

  ORDERS {
    bigint id PK
    string order_no UK
    bigint customer_id FK
    datetime order_datetime
    date delivery_date
    enum status "new|confirmed|allocated|purchased|shipped|invoiced|cancelled"
  }

  ORDER_ITEMS {
    bigint id PK
    bigint order_id FK
    bigint product_id FK
    numeric ordered_qty
    enum order_uom_type "uom_count|uom_kg"
    numeric estimated_weight_kg
    numeric actual_weight_kg
    enum pricing_basis "uom_count|uom_kg"
    numeric unit_price_uom_count
    numeric unit_price_uom_kg
    enum line_status "open|allocated|purchased|shipped|invoiced|cancelled"
  }

  SUPPLIER_ALLOCATIONS {
    bigint id PK
    bigint order_item_id FK
    bigint suggested_supplier_id
    bigint final_supplier_id
    numeric suggested_qty
    numeric final_qty
    boolean is_manual_override
    string override_reason_code
    numeric target_price
    enum stockout_policy "backorder|substitute|cancel|split"
    string split_group_id
    bigint parent_allocation_id FK
    boolean is_split_child
  }

  PURCHASE_RESULTS {
    bigint id PK
    bigint allocation_id FK
    bigint supplier_id
    numeric purchased_qty
    numeric actual_weight_kg
    numeric unit_cost
    numeric final_unit_cost
    string result_status
    numeric shortage_qty
    enum shortage_policy "backorder|substitute|cancel|split"
    boolean invoiceable_flag
  }

  INVOICES {
    bigint id PK
    string invoice_no UK
    bigint customer_id FK
    date invoice_date
    date delivery_date
    numeric subtotal
    numeric tax_total
    numeric grand_total
    enum status "draft|finalized|sent|cancelled"
  }

  INVOICE_ITEMS {
    bigint id PK
    bigint invoice_id FK
    bigint order_item_id FK
    numeric billable_qty
    string billable_uom
    enum invoice_line_status "uninvoiced|partially_invoiced|invoiced|cancelled"
    numeric sales_unit_price
    numeric unit_cost_basis
    numeric line_amount
    numeric tax_amount
  }
```

## Constraints (summary)
- `orders.order_no`, `products.sku`, `customers.customer_code`, `invoices.invoice_no`: UNIQUE
- `order_items.ordered_qty > 0`
- price-by-basis check:
  - `pricing_basis=uom_count` => `unit_price_uom_count` required
  - `pricing_basis=uom_kg` => `unit_price_uom_kg` required
- catch-weight line requires `actual_weight_kg` at invoice finalize.
