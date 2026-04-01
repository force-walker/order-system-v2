#!/usr/bin/env bash
set -euo pipefail

ROOT="$HOME/.openclaw/workspace/order_system_v2"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"
PYTHON_BIN="$HOME/.venvs_order_system_v2/bin/python3"
HOST_DATABASE_URL="postgresql+psycopg://postgres:postgres@127.0.0.1:5432/order_system_v2"

echo "==> move to project root: $ROOT"
cd "$ROOT"

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker not found"
  exit 1
fi

if ! command -v gnome-terminal >/dev/null 2>&1; then
  echo "ERROR: gnome-terminal not found"
  exit 1
fi

echo "==> start containers (db/redis)"
docker compose up -d db redis
docker compose ps

echo "==> stop api container (host uvicorn will use 8000)"
docker compose stop api || true

echo "==> verify external python venv"
if [ ! -x "$PYTHON_BIN" ]; then
  echo "ERROR: python not found at $PYTHON_BIN"
  exit 1
fi

echo "==> start backend (host uvicorn)"
gnome-terminal -- bash -lc "
cd '$BACKEND' &&
export DATABASE_URL='$HOST_DATABASE_URL' &&
PYTHONPATH=. '$PYTHON_BIN' -m alembic upgrade head &&
PYTHONPATH=. '$PYTHON_BIN' -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
exec bash
" || true

echo "==> ensure frontend dependencies (npm ci when node_modules absent)"
if [ ! -d "$FRONTEND/node_modules" ]; then
  (cd "$FRONTEND" && npm ci)
fi

echo "==> start frontend"
gnome-terminal -- bash -lc "
cd '$FRONTEND' &&
npm run dev -- --host 0.0.0.0 --port 5173
exec bash
" || true

echo ""
echo "✅ Started"
echo "Frontend: http://localhost:5173"
echo "Backend : http://localhost:8000"
echo "Docs    : http://localhost:8000/docs"
