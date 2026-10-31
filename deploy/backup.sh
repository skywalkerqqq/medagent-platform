#!/usr/bin/env sh
# 备份 SQLite（单文件 + WAL）。生产建议先停写或使用在线备份窗口。
set -eu
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
SOURCE="${1:-$ROOT/data/medagent.db}"
OUTDIR="${2:-$ROOT/data/backups}"
STAMP="$(date +%Y%m%d-%H%M%S)"
mkdir -p "$OUTDIR"
TARGET="$OUTDIR/medagent-$STAMP.db"
python3 - "$SOURCE" "$TARGET" <<'PY'
import sqlite3, sys
src = sqlite3.connect(sys.argv[1])
dst = sqlite3.connect(sys.argv[2])
src.backup(dst)
dst.close()
src.close()
PY
sha256sum "$TARGET" >> "$OUTDIR/SHA256SUMS.txt"
echo "备份完成：$TARGET"
