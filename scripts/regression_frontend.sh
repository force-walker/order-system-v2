#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/ikedakojiro/.openclaw/workspace/order_system_v2"
FRONTEND="$ROOT/frontend"

log(){ echo -e "\n==== $* ===="; }

log "0) 前提確認"
cd "$FRONTEND"
command -v npm >/dev/null

log "1) 依存解決"
npm ci --prefer-offline

log "2) 型チェック + build"
npm run build

log "3) Frontend単体テスト"
npm run test

echo -e "\n✅ frontend 回帰完了"
