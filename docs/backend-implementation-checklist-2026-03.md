# Backend Implementation Checklist (Revised)

Updated: 2026-03-27
Scope note: Odoo integration/data migration is **out of scope** for this project.

## A. Cross-OS operation (Linux Mint dev / Windows & macOS users)
- [ ] Docker-first startup path (OS-independent)
- [ ] `.env.example` with required keys + examples
- [ ] one-command startup documented

## B. Bulk APIs (required)
- [ ] bulk create
- [ ] bulk update
- [ ] bulk upsert
- [ ] bulk delete
- [ ] request item/count size limits documented
- [ ] idempotency policy documented

## C. Partial failure response model (required)
- [ ] `total / success / failed` summary
- [ ] per-row error detail: `index / field / code / message`
- [ ] 422 vs 500 semantics fixed
- [ ] human-readable error messages

## D. Simple external API contract
- [ ] API field names remain business-friendly and stable
- [ ] internal DB complexity is hidden from API consumers
- [ ] mapping/validation rules are explicit and testable

## E. CSV/JSON import
- [ ] unified import endpoint(s)
- [ ] row-level validation
- [ ] dry-run mode
- [ ] import report with detailed failures

## F. DB / migration health
- [ ] clean DB migration check on changes
- [ ] enum duplication avoidance rule in migration notes
- [ ] rollback path checked
- [ ] key index review for bulk operations

## G. Differential tests
- [ ] mapper/validation unit tests
- [ ] bulk API integration tests (including partial failures)
- [ ] migration smoke test

## Working rules
- 1 feature = 1 PR
- no requirements re-open; changes handled as proposal
- progress to `#08-progress-daily`
- bug reports to `#07-bug-report`
