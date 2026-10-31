#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${DSH_PYTHON:-python3}"
"$PY" tests/test_api.py
"$PY" tests/test_llm_live.py
"$PY" tests/test_dify.py
if command -v node >/dev/null 2>&1; then
  node --check web/app.js
  find miniprogram -name "*.js" -print0 | xargs -0 -n1 node --check
fi
echo "全部检查通过"

