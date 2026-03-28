#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/ikedakojiro/.openclaw/workspace/order_system_v2"

log(){ echo -e "\n==== $* ===="; }

cd "$ROOT"

log "1) Backend回帰"
./scripts/regression_check.sh

log "2) Frontend回帰"
./scripts/regression_frontend.sh

log "3) E2Eスモーク（任意）"
if [ -f "$ROOT/frontend/playwright.config.ts" ] || [ -f "$ROOT/frontend/playwright.config.js" ]; then
  (cd "$ROOT/frontend" && npx playwright test --grep @smoke)
else
  echo "playwright設定なしのためスキップ"
fi

echo -e "\n✅ 全体回帰完了"
