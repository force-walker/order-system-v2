#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/ikedakojiro/.openclaw/workspace/order_system_v2"
BACKEND="$ROOT/backend"

log(){ echo -e "
==== $* ===="; }

log "0) 前提確認"
cd "$ROOT"
docker-compose ps >/dev/null
log "1) アプリ回帰（host venv）"
cd "$BACKEND"
source .venv/bin/activate
python -m compileall app tests
PYTHONPATH=. python -m pytest -q tests

log "2) クリーンDB migration テスト"
cd "$ROOT"
docker-compose down -v
# DBだけ先に起動
docker-compose up -d db
# DB起動待ち（最大60秒）
for i in {1..30}; do
  if docker-compose exec -T db pg_isready -U "${POSTGRES_USER:-app}" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done
# APIコンテナ内で migration 実行
docker-compose run --rm api alembic upgrade head
docker-compose run --rm api alembic current
docker-compose run --rm api alembic heads

log "3) 再起動 idempotency テスト"
docker-compose down
docker-compose up -d
# APIヘルス待ち（最大60秒）
for i in {1..30}; do
  if curl -fsS http://localhost:8000/health >/dev/null; then
    break
  fi
  sleep 2
done
curl -i http://localhost:8000/health
# 2回目再起動でも落ちないことを確認
docker-compose down
docker-compose up -d
for i in {1..30}; do
  if curl -fsS http://localhost:8000/health >/dev/null; then
    break
  fi
  sleep 2
done
curl -i http://localhost:8000/health
log "4) コンテナ内スモーク（依存＆import確認）"
docker-compose run --rm api python -c "import app; print('app import ok')"
docker-compose run --rm api python -c "from app.main import app; print('main app import ok')"

echo -e "
✅ すべて完了"
