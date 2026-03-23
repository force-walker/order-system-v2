# ADR-0002: Status Transition Policy

- Status: Accepted
- Date: 2026-03-22

## Context
Requirement v2 fixed lifecycle and transition behavior. Implementation must preserve consistency and replay safety.

## Decision
- Canonical order status:
  `new -> confirmed -> allocated -> purchased -> shipped -> invoiced` (+ `cancelled`)
- Canonical line status:
  `open -> allocated -> purchased -> shipped -> invoiced` (+ `cancelled`)
- Line-first updates.
- Order-level transitions only via explicit user-triggered bulk actions.
- No automatic order promotion from line aggregation in MVP.
- If no eligible lines updated, return `409 STATUS_NO_TARGET_LINES`.

## Consequences
- Pros: predictable operations, explicit control, lower hidden automation risk.
- Cons: users must execute transition actions intentionally.

## References
- `docs/architecture/02-status-model.md`
- `docs/requirements-definition-closure-v2.md`
