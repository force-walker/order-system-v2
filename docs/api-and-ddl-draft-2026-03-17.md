# API Paths + DDL Draft (MVP v2)

Date: 2026-03-17

## API Paths (OpenAPI paths 想定)

### Auth
- POST `/api/v1/auth/login`
- POST `/api/v1/auth/refresh`
- POST `/api/v1/auth/logout`
- GET `/api/v1/auth/me`

### Master
- GET `/api/v1/products`
- GET `/api/v1/products/{productId}`
- POST `/api/v1/products`
- PATCH `/api/v1/products/{productId}`
- GET `/api/v1/customers`
- GET `/api/v1/customers/{customerId}`
- POST `/api/v1/customers`
- PATCH `/api/v1/customers/{customerId}`

### Orders
- GET `/api/v1/orders`
- POST `/api/v1/orders`
- GET `/api/v1/orders/{orderId}`
- PATCH `/api/v1/orders/{orderId}`
- POST `/api/v1/orders/{orderId}/confirm`
- POST `/api/v1/orders/{orderId}/cancel`
- GET `/api/v1/orders/{orderId}/items`
- POST `/api/v1/orders/{orderId}/items`
- PATCH `/api/v1/orders/{orderId}/items/{itemId}`
- POST `/api/v1/orders/{orderId}/items/{itemId}/cancel`

### Transitions (明示バルク)
- POST `/api/v1/transitions/orders/confirmed-to-allocated`
- POST `/api/v1/transitions/orders/allocated-to-purchased`
- POST `/api/v1/transitions/orders/purchased-to-shipped`
- POST `/api/v1/transitions/orders/shipped-to-invoiced`

### Allocation
- POST `/api/v1/allocations/runs`
- GET `/api/v1/allocations`
- PATCH `/api/v1/allocations/{allocationId}`
- POST `/api/v1/allocations/{allocationId}/split`

### Purchase results
- GET `/api/v1/purchase-results`
- POST `/api/v1/purchase-results`
- PATCH `/api/v1/purchase-results/{resultId}`
- POST `/api/v1/purchase-results/bulk-upsert`

### Invoices
- POST `/api/v1/invoices/generate`
- GET `/api/v1/invoices`
- GET `/api/v1/invoices/{invoiceId}`
- PATCH `/api/v1/invoices/{invoiceId}`
- POST `/api/v1/invoices/{invoiceId}/finalize`
- POST `/api/v1/invoices/{invoiceId}/reset-to-draft`
- POST `/api/v1/invoices/{invoiceId}/unlock`
- GET `/api/v1/invoices/{invoiceId}/items`
- PATCH `/api/v1/invoices/{invoiceId}/items/{itemId}`

### Audit / Ops
- GET `/api/v1/audit-logs`
- GET `/api/v1/health`
- GET `/api/v1/metrics`

## DDL Draft (PostgreSQL)

```sql
create type order_status as enum ('new','confirmed','allocated','purchased','shipped','invoiced','cancelled');
create type line_status as enum ('open','allocated','purchased','shipped','invoiced','cancelled');
create type pricing_basis as enum ('uom_count','uom_kg');
create type stockout_policy as enum ('backorder','substitute','cancel','split');
create type invoice_status as enum ('draft','finalized','sent','cancelled');
create type invoice_line_status as enum ('uninvoiced','partially_invoiced','invoiced','cancelled');

-- (詳細DDLは migration files を参照)
```

## 実装ファイル
- `backend/alembic/versions/2026031701_core_v2_alignment.py`
- `backend/alembic/versions/2026031702_allocation_v2_alignment.py`
- `backend/alembic/versions/2026031703_invoice_v2_alignment.py`
- `backend/alembic/versions/2026031704_audit_v2_alignment.py`
