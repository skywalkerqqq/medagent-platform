#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
PORT="${1:-8090}"
PY="${DSH_PYTHON:-python3}"
exec "$PY" server/app.py --port "$PORT" --db data/medagent.db --reset
