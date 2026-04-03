# Runtime Environment Notes

Updated: 2026-04-02

## Python virtual environment policy

For this repository, backend Python venv is managed **outside** `backend/`.

- Do **not** assume `backend/.venv`
- Use:
  - `/home/ikedakojiro/.venvs_order_system_v2/bin/python3`
  - `/home/ikedakojiro/.venvs_order_system_v2/bin/pip`

Optional activation:

```bash
source /home/ikedakojiro/.venvs_order_system_v2/bin/activate
```

## Frontend dependency policy (`node_modules`)

`frontend/node_modules` is treated as disposable dependency cache.

- Do **not** assume `frontend/node_modules` exists
- Install only when needed:
  - `cd frontend && npm ci`
- Remove when not needed:
  - `cd frontend && rm -rf node_modules`
- Do not inspect/edit files inside `node_modules` as project source
- Prefer `npm ci` over `npm install` for reproducible setup

## Backend launch reference

```bash
cd /home/ikedakojiro/.openclaw/workspace/order_system_v2/backend
PYTHONPATH=. /home/ikedakojiro/.venvs_order_system_v2/bin/python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Alembic reference

```bash
cd /home/ikedakojiro/.openclaw/workspace/order_system_v2/backend
DATABASE_URL=postgresql+psycopg://postgres:postgres@127.0.0.1:5432/order_system_v2 \
  /home/ikedakojiro/.venvs_order_system_v2/bin/python3 -m alembic upgrade head
```
