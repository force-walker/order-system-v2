# Environment Definition (Restart Baseline)

## Current policy (until MVP release)

- No public deployment yet.
- We operate with **local + CI** only.
- Staging/Production are defined as placeholders for future rollout.

## Environments

### local
- Purpose: development and debugging
- Runtime: Docker Compose on developer machine
- Services: api, db, redis, worker
- Config source: `backend/.env` (local only)

### staging (placeholder)
- Purpose: pre-production verification
- Not deployed yet
- GitHub Environment: `staging` (can be created now without real secrets)

### production (placeholder)
- Purpose: live operation
- Not deployed yet
- GitHub Environment: `production`
- Required reviewers must be enabled before first prod deploy

## Promotion flow

1. Develop on `rebuild/order-system`
2. Open PR to `main`
3. CI required checks pass (lint/test)
4. Merge after review

## Notes

- `.env` must never be committed.
- `.env.example` should keep only non-secret sample values.
- Branch protection and review rules are enforced on `main`.
