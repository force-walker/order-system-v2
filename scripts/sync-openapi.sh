#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${ORDER_SYSTEM_PYTHON:-$HOME/.venvs_order_system_v2/bin/python3}"

test -x "$PYTHON_BIN" || { echo "Python missing: $PYTHON_BIN" >&2; exit 1; }
"$PYTHON_BIN" "$PROJECT_ROOT/scripts/export_openapi.py"
npm --prefix "$PROJECT_ROOT/frontend" run gen:types
