# Permanent document / line numbering migration

Approved: 2026-09-20
Implemented migrations: `2026092002` → `2026092007`

## Authoritative identifiers

| Scope | Authoritative value | Purpose |
|---|---|---|
| Internal entity | UUID `id` / UUID FK | PK, FK, API routing, audit linkage |
| Header business sequence | `document_seq` | Immutable permanent numeric sequence |
| Detail within parent | `line_no` | Immutable business line number |
| Human-readable detail reference | `line_ref` | Globally unique reference for screens, PDF, CSV and integrations |

`line_no` has `CHECK (line_no > 0)` and `UNIQUE (parent_id, line_no)`. Automatic allocation is `10, 20, 30 ...`, but the database deliberately does not require multiples of ten; a future line such as `15` can be inserted without renumbering existing lines. Sorting must never rewrite `line_no` or `line_ref`. A future UI-only sort order must use a separate field such as `display_order`.

## Formats and independent sequences

| Document | Sequence | Header format | Detail format |
|---|---|---|---|
| Order | `order_document_seq` | `ORD-00000001` | `ODL-00000001-0010` |
| Delivery | `delivery_document_seq` | `DEL-00000001` | `DLI-00000001-0010` |
| Invoice Draft | `invoice_document_seq` | `IVD-00000001` | `IVL-00000001-0010` |
| Official Invoice | `official_invoice_document_seq` | `INV-00000001` | uses the Draft's existing items |

Official Invoice sequence allocation occurs only on the first Finalize. Reset to Draft does not erase the allocated official sequence or number. Re-Finalize reuses it and does not consume another sequence value.

`invoice_document_seq` and `official_invoice_document_seq` are independent sequences. Their numeric portions are not expected to match. For example, the following pair is normal and valid:

```text
IVD-00000125
INV-00000097
```

The Draft number expresses the order in which invoice drafts were created, while the Official number expresses the order in which invoices first received an official number. Draft creation never reserves an Official sequence value.

Concurrency-safe legacy ID sequences are `orders_legacy_id_seq`, `order_items_legacy_id_seq`, `invoices_legacy_id_seq`, and `invoice_items_legacy_id_seq`.

## Deprecated compatibility fields

`order_line_no`, `delivery_line_no`, and `invoice_line_no` remain during the migration period. Existing values are never rewritten. For a new row, the application mirrors `line_ref` into the old column only for **field compatibility**. This does not preserve the historical value format. New code must use UUID `id`, `line_no`, and `line_ref`; searches, reports, PDF, CSV, and future integrations must use `line_ref`.

## Migration order and validation

1. `2026092002`: create independent PostgreSQL sequences and nullable foundation columns; add nullable `invoices.delivery_id` UUID FK while retaining compatibility strings.
2. `2026092003`: deterministically backfill `document_seq`, `line_no`, `line_ref`, and `next_line_no`; preserve every UUID and old number string; advance each sequence to the existing maximum.
3. `2026092004`: validate backfill completeness; add NOT NULL, positive, parent-scoped uniqueness and global `line_ref` uniqueness constraints; install sequence defaults for legacy IDs.
4. Backend / Frontend switch: allocate from sequences and parent row counters; expose and display `line_ref`; prefer `invoices.delivery_id` over delivery-number lookup.
5. `2026092005`: validate that no header is empty; add deferred PostgreSQL constraint triggers and immutable business-number triggers.
6. `2026092006`: serialize deferred Detail deletion checks with a `FOR UPDATE` Header lock; make issued Header business-number strings immutable; align SQLAlchemy NOT NULL metadata with the database.
7. `2026092007`: enforce the PostgreSQL-level consistency of `order_no`, `delivery_no`, and `invoice_draft_no` with their Header `document_seq` on INSERT and whenever either value changes. Unchanged legacy backfill number strings remain valid.

Every Header + Detail creation path uses one database transaction. Header-only Order and Invoice creation APIs are deprecated and return `422`. Application checks reject deletion of the last Order detail; deferred database triggers protect Order, Delivery, and Invoice aggregates at commit even when SQL bypasses the API.

The deferred Detail trigger locks the affected Header before checking for remaining Detail rows. Concurrent transactions deleting the final two rows are therefore serialized: one commit succeeds and the other is rejected, leaving at least one Detail row.

## Delivery cardinality

This phase retains `Delivery.order_id UNIQUE` and `DeliveryItem.order_item_id UNIQUE` (Order 1:1 Delivery and OrderItem 1:1 DeliveryItem). `document_seq`, `delivery_no`, `line_no`, and `line_ref` do not encode the Order number or a branch derived from it, so a later 1:N Delivery phase can remove those two uniqueness constraints without renumbering existing Delivery records or redesigning this numbering schema.
