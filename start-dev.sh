#!/usr/bin/env bash
set -euo pipefail

ROOT="$HOME/.openclaw/workspace/order_system_v2"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"

HOST_DATABASE_URL="postgresql+psycopg://postgres:postgres@127.0.0.1:5432/order_system_v2"

echo "==> move to project root: $ROOT"
cd "$ROOT"

echo "==> check docker"
if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker not found"
  exit 1
fi

echo "==> start containers"
docker compose up -d
docker compose ps

echo "==> start backend"
gnome-terminal -- bash -lc "
cd '$BACKEND' &&
source .venv/bin/activate &&
export DATABASE_URL='$HOST_DATABASE_URL' &&
( [ -f requirements.txt ] && pip install -r requirements.txt || true ) &&
( command -v alembic >/dev/null 2>&1 && alembic upgrade head || true ) &&
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000;
exec bash
" || true

echo "==> start frontend"
gnome-terminal -- bash -lc "
cd '$FRONTEND' &&
npm install &&
npm run dev -- --host 0.0.0.0 --port 5173;
exec bash
" || true

echo ""
echo "✅ Started"
echo "Frontend: http://localhost:5173"
echo "Backend : http://localhost:8000"
echo "Docs    : http://localhost:8000/docs"
