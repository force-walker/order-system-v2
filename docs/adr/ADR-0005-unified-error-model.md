# ADR-0005: Unified Error Model

- Status: Accepted
- Date: 2026-03-22

## Context
Inconsistent API errors slow down frontend integration and incident handling.

## Decision
Adopt unified error response:
```json
{ "code": "...", "message": "...", "details": {}, "traceId": "..." }
```
Use standard HTTP families for MVP:
`400/401/403/404/409/422` (+ `500` for unexpected internal failures).
Include business codes such as `STATUS_NO_TARGET_LINES`.

## Consequences
- Pros: consistent client handling and better observability.
- Cons: requires strict discipline to keep codes stable and synchronized.

## References
- `docs/architecture/06-error-model.md`
- `docs/api-error-codes-draft.md`
