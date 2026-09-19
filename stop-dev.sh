#!/usr/bin/env bash
set -euo pipefail
export COMPOSE_API_VERSION=1.44
PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"
systemctl --user stop order-system-v2-frontend.service order-system-v2-api.service 2>/dev/null || true
docker-compose -p order_system_v2 -f docker-compose.dev.yml stop db redis
echo 'Stopped. Database and backups are preserved.'
