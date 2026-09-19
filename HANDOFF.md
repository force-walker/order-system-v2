# order_system_v2 handoff

Updated: 2026-09-19

## Active workspace

- Repository: `/home/ikedakojiro/Documents/ChatGPT/order_system_v2`
- Branch: `codex/remote-development`
- Remote: `origin` (`force-walker/order-system-v2`)
- The former OpenClaw workspace remains only as a fallback. Do not run both copies.
- Never display, copy, log, or commit `backend/.env`.

## Current runtime

- Backend: FastAPI, SQLAlchemy, Alembic, PostgreSQL 16, Redis
- Frontend: React 18, Vite, TypeScript, Vitest
- Authentication: user ID/password with DB-backed, revocable bearer sessions
- Remote development: Tailscale; Vite listens on the Tailscale IPv4 and proxies `/api` and `/health` to the loopback API
- PostgreSQL and Redis listen on loopback only

Start and stop from the repository root:

```bash
./start-dev.sh
./stop-dev.sh
```

`start-dev.sh` reuses the external `order_system_v2_pgdata` volume, stops application writes, creates a private dump in `.local/backups/`, applies Alembic migrations, and starts the API and frontend as user systemd transient services. It does not read or copy `backend/.env`.

Detailed procedures:

- `docs/remote-development.md`
- `docs/remote-user-guide.md`
- `docs/authentication.md`
- `docs/audit-identity-repair.md`
- `docs/uuid-frontend-repair.md`

## Authentication behavior

- Self-registration creates an independent `auth_users` record with role `order_entry`.
- Registration does not create, modify, or associate a Customer.
- Passwords use salted PBKDF2-HMAC-SHA256 hashes.
- Access and refresh tokens are random opaque values; only SHA-256 hashes are stored.
- All business API routers require authentication; `/health` remains public.
- Logout revokes the server session and clears the browser session immediately.
- `EMAIL_VERIFICATION_REQUIRED=true` fails closed because email delivery/verification is not implemented.

## ID model

Orders, order items, invoices, invoice items, deliveries, and delivery items use UUID strings. Customer, product, supplier, allocation, purchase-result, and audit IDs remain numeric. Frontend code must preserve UUIDs as strings and must not convert route IDs with `Number(...)`.

## Database repair

Migration `2026091801` restores PostgreSQL identity generation for `audit_logs.id`, which was lost in a historical UUID migration. The live database was backed up before migration and existing records were preserved. PostgreSQL regression tests use isolated rollback-only schemas when `TEST_POSTGRES_URL` is provided.

## Verification commands

Backend, isolated from live business data:

```bash
cd backend
DATABASE_URL=sqlite+pysqlite:///:memory: /home/ikedakojiro/.venvs_order_system_v2/bin/python3 -m pytest -q
```

Frontend:

```bash
cd frontend
npm run typecheck
npm run test
VITE_API_BASE_URL='' VITE_USE_MOCK=false VITE_APP_BRANCH=codex/remote-development npm run build
```

Other checks:

```bash
git diff --check
bash -n start-dev.sh stop-dev.sh
```

After changing backend routes or schemas, synchronize the committed API contract and frontend types:

```bash
cd frontend
npm run sync:openapi
```

## Project rules

- Check `git status --short --branch` before editing.
- Preserve unrelated user changes and business data.
- Never expose `backend/.env`, credentials, tokens, Tailscale invites, or database backups.
- Use the current workspace, not the OpenClaw fallback.
- Keep the frontend branch label current.
- Run focused tests and then the relevant full suite before committing.
- Treat migrations and cleanup commands as data-sensitive operations.

## Known remaining product risks

- Fine-grained role permissions and customer-level data isolation are incomplete.
- Self-registration is suitable only for trusted development users on the tailnet.
- Email verification delivery, password reset, MFA, rate limiting, and session cleanup are not implemented.
- Tokens are stored in localStorage; production deployment requires HTTPS and a security review.
- Allocation eligibility is not yet restricted to confirmed orders at both display and API-save layers.
- The purchase-to-invoice-draft flow has a separate API contract mismatch (`purchase_result_ids` / `invoice_id`) and requires dedicated repair and tests.
- The frontend production bundle still emits the existing large-chunk warning.

## Recent completed work

- Navigation selection and stable wide layout
- Order list `new -> confirmed` action
- UUID-safe order/invoice navigation, editing, selections, and service payloads
- Password registration/login/logout and protected routes/APIs
- Shared order identifier lookup with legacy numeric fallback
- Audit-log identity repair
- Tailscale-oriented host startup and user documentation
