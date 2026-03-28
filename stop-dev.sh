#!/usr/bin/env bash
set -euo pipefail
cd "$HOME/.openclaw/workspace/order_system_v2"
docker compose down
echo "✅ docker compose down done"
echo "※ backend/frontend は各ターミナルで Ctrl+C で停止"
