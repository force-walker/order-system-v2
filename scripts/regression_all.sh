#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/ikedakojiro/.openclaw/workspace/order_system_v2"

log(){ echo -e "\n==== $* ===="; }

cd "$ROOT"

# Build mode auto decision (default)
# - API依存系変更あり: API_BUILD_MODE=no-cache
# - それ以外の変更のみ: SKIP_API_BUILD=1
# - 明示指定がある場合はそれを優先
if [[ "${AUTO_BUILD_MODE:-1}" == "1" ]]; then
  if [[ -z "${SKIP_API_BUILD:-}" && -z "${API_BUILD_MODE:-}" ]]; then
    changed_files="$(git diff --name-only; git diff --name-only --cached; git ls-files --others --exclude-standard)"
    if echo "$changed_files" | grep -Eq '(^|/)(requirements(\.txt|-dev\.txt)?|Dockerfile|docker-compose\.ya?ml)$'; then
      export API_BUILD_MODE="no-cache"
      echo "[auto] dependency/container change detected -> API_BUILD_MODE=no-cache"
    else
      export SKIP_API_BUILD="1"
      echo "[auto] app/test change only -> SKIP_API_BUILD=1"
    fi
  fi
fi

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
