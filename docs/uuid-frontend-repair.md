# Frontend UUID handling repair (2026-09-19)

- Orders, order items, invoices and invoice items use UUID strings in the API.
- Customer, product, supplier, allocation and purchase-result IDs remain numeric.
- `EntityId` preserves UUID strings while allowing legacy numeric/mock identifiers.
- Route parameters are no longer converted with `Number`; order editing retains existing item IDs for PATCH rather than recreating items.
- Selection state, allocation error mapping, shipping PDF selections and purchase/order associations retain UUIDs.
- Lists compare dates/document numbers rather than subtracting UUIDs. Invoice list and previous/next navigation share the same ordering.
- No database migration or business-data mutation is part of this repair.

Regression tests: `UuidRoutes.test.tsx` and `uuidServices.test.ts` cover routes, editing, invoice finalization IDs, allocation payloads/errors, PDF selections and ordering. These use mocked services/API responses, not live business records.

Out of scope: the separately identified purchase-to-invoice-draft API contract mismatch (required `purchase_result_ids` and response `invoice_id`) is not repaired here. Fixing UUID handling alone does not establish that the whole delivery-to-invoice flow works. Allocation eligibility by confirmed status is also unchanged.
