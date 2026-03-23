# ADR-0003: Dual-UOM and Catch-Weight Model

- Status: Accepted
- Date: 2026-03-22

## Context
Business requires quantity/weight mixed operations and accurate billing at finalize time.

## Decision
Adopt Dual-UOM as first-class model:
- `uom_count` / `uom_kg`
- `unit_price_uom_count` / `unit_price_uom_kg`
- Catch-weight items require `actual_weight_kg` before invoice finalize.

## Consequences
- Pros: supports real operations and mixed billing scenarios.
- Cons: added validation and data model complexity.

## References
- `docs/architecture/04-db-core-tables.md`
- `docs/db-dual-uom-draft.md`
