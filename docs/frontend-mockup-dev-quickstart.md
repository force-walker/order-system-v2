# Frontend Mockup Dev Quickstart (Backend-side prerequisites)

Updated: 2026-03-27

This guide provides:
1. seed data path for frontend mockup
2. temporary auth operation rule (admin login flow)

## 1) Start backend stack

From repo root:

```bash
docker-compose up -d db redis
cd backend
DATABASE_URL=postgresql+psycopg://postgres:postgres@127.0.0.1:5432/order_system_v2 .venv/bin/alembic upgrade head
PYTHONPATH=. .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## 2) Seed frontend mock data

From `backend/`:

```bash
PYTHONPATH=. DATABASE_URL=postgresql+psycopg://postgres:postgres@127.0.0.1:5432/order_system_v2 \
  .venv/bin/python scripts/seed_frontend_mock_data.py
```

Seeded entities:
- products (2)
- customer (1)
- order + order_item (1)
- supplier_allocation (1)
- purchase_result (1)
- invoice (1)
- batch_job (1)

## 3) Temporary auth rule for frontend development

Use login API (no hardcoded JWT in source):

```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "user_id": "frontend-dev-admin",
  "role": "admin"
}
```

Response returns:
- `access_token`
- `refresh_token`
- `token_type` (`bearer`)
- `expires_in`

Use access token in requests:

```http
Authorization: Bearer <access_token>
```

Refresh when needed:

```http
POST /api/v1/auth/refresh
{ "refresh_token": "..." }
```

## 4) Suggested frontend env vars

```bash
VITE_API_BASE_URL=http://127.0.0.1:8000
VITE_DEV_LOGIN_USER=frontend-dev-admin
VITE_DEV_LOGIN_ROLE=admin
```

## 5) Contract reminder

For mockup phase, treat API as frozen by:
- `docs/frontend-api-contract-freeze-2026-03.md`
- `docs/openapi-mvp-skeleton-draft.yaml`
