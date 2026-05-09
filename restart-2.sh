#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

log(){ echo -e "\n==== $* ===="; }

log "0) stop existing services"
docker-compose down || true

log "1) start db/redis"
docker-compose up -d db redis

log "2) wait db healthy"
for i in {1..60}; do
  if docker-compose exec -T db pg_isready -U "${POSTGRES_USER:-app}" >/dev/null 2>&1; then
    break
  fi
  sleep 1
  if [[ "$i" == "60" ]]; then
    echo "[error] db not ready"
    docker-compose ps || true
    docker-compose logs --tail=120 db || true
    exit 1
  fi
done

log "3) start api"
docker-compose up -d api

log "4) wait api health"
ok=0
for i in {1..90}; do
  if curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; then
    ok=1
    break
  fi
  sleep 1
done

if [[ "$ok" -ne 1 ]]; then
  echo "[error] api health timeout"
  docker-compose ps || true
  docker-compose logs --tail=200 api || true
  exit 1
fi

log "5) ready"
docker-compose ps
curl -i http://127.0.0.1:8000/health

echo -e "\n✅ restart-2 done: UI should be usable"
