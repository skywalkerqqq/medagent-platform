#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${DSH_PYTHON:-python3}"
"$PY" tests/test_api.py
if command -v node >/dev/null 2>&1; then
  node --check web/app.js
fi
echo "全部检查通过"
