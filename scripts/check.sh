#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${MEDAGENT_PYTHON:-python3}"
"$PY" tests/test_api.py
"$PY" tests/test_llm_live.py
"$PY" tests/test_dify.py
"$PY" tests/test_notify.py
"$PY" tests/test_rate_limit.py
"$PY" tests/test_pg_compat.py
"$PY" tests/test_pg_migration.py
"$PY" tests/test_production_import.py
if command -v node >/dev/null 2>&1; then
  node --check web/app.js
  find miniprogram -name "*.js" -print0 | xargs -0 -n1 node --check
fi
echo "全部检查通过"

