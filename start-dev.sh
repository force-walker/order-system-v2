#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${ORDER_SYSTEM_PYTHON:-$HOME/.venvs_order_system_v2/bin/python3}"
export DATABASE_URL='postgresql+psycopg://postgres:postgres@127.0.0.1:5432/order_system_v2'
# Compose 1.x needs the pre-1.45 image-inspection response on this Docker host.
export COMPOSE_API_VERSION=1.44
cd "$PROJECT_ROOT"

for executable in docker-compose systemd-run systemctl tailscale curl npm; do
  command -v "$executable" >/dev/null || { echo "Missing: $executable"; exit 1; }
done
test -x "$PYTHON_BIN" || { echo "Python missing: $PYTHON_BIN"; exit 1; }
systemctl --user show-environment >/dev/null
DEV_HOST="${ORDER_SYSTEM_DEV_HOST:-$(tailscale ip -4)}"
test -n "$DEV_HOST" || { echo 'Tailscale IPv4 unavailable'; exit 1; }
if [ ! -d frontend/node_modules ]; then
  (cd frontend && npm ci)
fi

docker-compose -p order_system_v2 -f docker-compose.dev.yml up -d db redis
for attempt in {1..30}; do
  if docker-compose -p order_system_v2 -f docker-compose.dev.yml exec -T db pg_isready -U postgres -d order_system_v2 >/dev/null; then
    break
  fi
  if [ "$attempt" = 30 ]; then echo 'Database not ready'; exit 1; fi
  sleep 1
done

# Stop application writes before taking a backup and applying migrations.
systemctl --user stop order-system-v2-api.service order-system-v2-frontend.service 2>/dev/null || true
systemctl --user reset-failed order-system-v2-api.service order-system-v2-frontend.service 2>/dev/null || true

# Back up before applying migrations. Backups can contain business data.
mkdir -p .local/backups
chmod 700 .local .local/backups
backup_path="$PROJECT_ROOT/.local/backups/pre-start-$(date +%Y%m%d-%H%M%S)-$$.dump"
(umask 077; docker-compose -p order_system_v2 -f docker-compose.dev.yml exec -T db pg_dump -U postgres -d order_system_v2 -Fc > "$backup_path")
(cd backend && PYTHONPATH=. "$PYTHON_BIN" -m alembic upgrade head)
# Forward explicit auth policy settings without overriding user-manager defaults.
AUTH_ENV_ARGS=()
for auth_setting in EMAIL_VERIFICATION_REQUIRED JWT_ACCESS_TTL_SECONDS JWT_REFRESH_TTL_SECONDS; do
  if [[ -v "$auth_setting" ]]; then
    AUTH_ENV_ARGS+=("--setenv=$auth_setting=${!auth_setting}")
  fi
done
systemd-run --user --unit=order-system-v2-api --collect \
  "${AUTH_ENV_ARGS[@]}" \
  --working-directory="$PROJECT_ROOT/backend" \
  --setenv="DATABASE_URL=$DATABASE_URL" --setenv=PYTHONPATH=. \
  --property=Restart=on-failure \
  "$PYTHON_BIN" -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
systemd-run --user --unit=order-system-v2-frontend --collect \
  --setenv="ORDER_SYSTEM_DEV_HOST=$DEV_HOST" \
  --working-directory="$PROJECT_ROOT/frontend" --property=Restart=on-failure \
  "$(command -v npm)" run dev

for attempt in {1..30}; do
  if curl -fsS --max-time 2 "http://$DEV_HOST:5173/health" >/dev/null 2>&1 && \
     curl -fsS --max-time 2 "http://$DEV_HOST:5173/" >/dev/null 2>&1; then
    echo "Ready (host and remote): http://$DEV_HOST:5173"
    echo 'Remote access: see docs/remote-development.md.'
    exit 0
  fi
  sleep 1
done
echo 'Startup failed. Check: journalctl --user -u order-system-v2-api -u order-system-v2-frontend -n 50'
exit 1
