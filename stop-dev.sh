#!/usr/bin/env bash
set -euo pipefail

ROOT="$HOME/.openclaw/workspace/order_system_v2"
FRONTEND="$ROOT/frontend"
CLEAN_NODE_MODULES="${1:-}"

cd "$ROOT"

echo "==> stop docker compose services"
docker-compose down

echo "==> note"
echo "backend/frontend terminals should be stopped with Ctrl+C if still running"

if [ "$CLEAN_NODE_MODULES" = "--clean-node-modules" ]; then
  echo "==> remove frontend/node_modules"
  rm -rf "$FRONTEND/node_modules"
fi

echo "✅ stop complete"
