"""PostgreSQL 运行时兼容层（实验性，Stage 2）。

通过 `DATABASE_URL=postgresql://...` 启用；把现有 SQLite 风格 SQL 适配到 psycopg：
- `?` → `%s`（跳过字符串字面量内的问号）；
- `INSERT OR IGNORE` → `ON CONFLICT DO NOTHING`；
- 对有 BIGSERIAL id 的表，INSERT 自动追加 `RETURNING id` 以兼容 `cursor.lastrowid`；
- Row 同时支持下标与列名访问（兼容 sqlite3.Row 用法）。

边界：单连接/无连接池；SQLite 专有初始化（PRAGMA/WAL）不执行；尚未在真实 PG 实例上验证，
必须先跑 `tests/test_pg_runtime.py`（PG_TEST_URL）与双跑对账，不能直接上生产。
"""
from __future__ import annotations

import os
import re


def enabled() -> bool:
    url = (os.environ.get("DATABASE_URL") or "").strip()
    return url.startswith(("postgres://", "postgresql://"))


def dsn() -> str:
    return (os.environ.get("DATABASE_URL") or "").strip()


def convert_schema(sql: str) -> str:
    converted = re.sub(r"\bINTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT\b", "BIGSERIAL PRIMARY KEY", sql,
                       flags=re.IGNORECASE)
    converted = re.sub(r"\bAUTOINCREMENT\b", "", converted, flags=re.IGNORECASE)
    converted = re.sub(r"\bREAL\b", "DOUBLE PRECISION", converted, flags=re.IGNORECASE)
    converted = re.sub(r"\bDATETIME\b", "TIMESTAMPTZ", converted, flags=re.IGNORECASE)
    return converted


def split_statements(script: str) -> list[str]:
    statements, current = [], []
    quote = None
    for char in script:
        if quote:
            current.append(char)
            if char == quote:
                quote = None
            continue
        if char in ("'", '"'):
            quote = char
            current.append(char)
            continue
        if char == ";":
            statement = "".join(current).strip()
            if statement:
                statements.append(statement)
            current = []
        else:
            current.append(char)
    tail = "".join(current).strip()
    if tail:
        statements.append(tail)
    return statements


def convert_placeholders(sql: str) -> str:
    output, quote = [], None
    for char in sql:
        if quote:
            output.append(char)
            if char == quote:
                quote = None
            continue
        if char in ("'", '"'):
            quote = char
            output.append(char)
            continue
        if char == "?":
            output.append("%s")
        else:
            output.append(char)
    return "".join(output)


def prepare_sql(sql: str, serial_tables: set[str]) -> tuple[str, bool]:
    """返回 (可执行 SQL, 是否自动 RETURNING id)。"""
    raw = sql.strip()
    conflict = bool(re.match(r"^INSERT\s+OR\s+IGNORE\s+INTO\b", raw, flags=re.IGNORECASE))
    if conflict:
        raw = re.sub(r"^INSERT\s+OR\s+IGNORE\s+INTO\b", "INSERT INTO", raw, count=1, flags=re.IGNORECASE)
        raw = raw.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"
    returning = False
    if re.match(r"^INSERT\s+INTO\b", raw, flags=re.IGNORECASE) and "RETURNING" not in raw.upper():
        match = re.match(r'^INSERT\s+INTO\s+"?([A-Za-z_][A-Za-z0-9_]*)"?', raw, flags=re.IGNORECASE)
        table = (match.group(1).lower() if match else "")
        if table in serial_tables:
            raw = raw.rstrip().rstrip(";") + " RETURNING id"
            returning = True
    return convert_placeholders(raw), returning


class PGRow:
    """兼容 sqlite3.Row：row[0] / row["col"] / dict(row) / keys()。"""

    __slots__ = ("_values", "_mapping")

    def __init__(self, columns, values):
        self._values = tuple(values)
        self._mapping = dict(zip(columns, values))

    def __getitem__(self, key):
        return self._values[key] if isinstance(key, int) else self._mapping[key]

    def __iter__(self):
        return iter(self._values)

    def __len__(self):
        return len(self._values)

    def keys(self):
        return self._mapping.keys()

    def get(self, key, default=None):
        return self._mapping.get(key, default)

    def __repr__(self):
        return f"PGRow({self._mapping})"


class PGCursor:
    def __init__(self, cursor, lastrowid=None):
        self._cursor = cursor
        self.lastrowid = lastrowid
        self.rowcount = cursor.rowcount

    @property
    def description(self):
        return self._cursor.description

    def _columns(self):
        return [item.name for item in (self._cursor.description or [])]

    def fetchone(self):
        row = self._cursor.fetchone()
        return PGRow(self._columns(), row) if row is not None else None

    def fetchall(self):
        columns = self._columns()
        return [PGRow(columns, row) for row in self._cursor.fetchall()]

    def close(self):
        self._cursor.close()


class PGConn:
    def __init__(self):
        try:
            import psycopg
        except ImportError as exc:  # pragma: no cover - 环境相关
            raise RuntimeError("DATABASE_URL 指向 PostgreSQL，但未安装 psycopg；"
                               "请安装 'psycopg[binary]'（production/requirements-migration.txt）") from exc
        self._psycopg = psycopg
        self._conn = psycopg.connect(dsn())
        self._serial_tables = self._load_serial_tables()

    def _load_serial_tables(self) -> set[str]:
        with self._conn.cursor() as cursor:
            cursor.execute(
                "SELECT table_name FROM information_schema.columns "
                "WHERE table_schema='public' AND column_name='id' AND column_default LIKE 'nextval%'"
            )
            return {row[0].lower() for row in cursor.fetchall()}

    def execute(self, sql: str, params=()):
        if not re.match(r"^\s*(SELECT|INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|WITH|PRAGMA)\b", sql, flags=re.IGNORECASE):
            # 兼容 BEGIN/COMMIT 等控制语句
            pass
        prepared, returning = prepare_sql(sql, self._serial_tables)
        cursor = self._conn.cursor()
        cursor.execute(prepared, params or ())
        lastrowid = None
        if returning:
            row = cursor.fetchone()
            lastrowid = row[0] if row else None
        return PGCursor(cursor, lastrowid)

    def executemany(self, sql: str, seq):
        prepared, _ = prepare_sql(sql, self._serial_tables)
        cursor = self._conn.cursor()
        cursor.executemany(prepared, list(seq))
        return PGCursor(cursor)

    def executescript(self, script: str):
        for statement in split_statements(convert_schema(script)):
            self.execute(statement)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()


def connect() -> PGConn:
    return PGConn()


def init_schema(schema_sql: str, reset: bool = False) -> None:
    """初始化 PG schema；reset=True 会 DROP public schema（仅专用迁移库/测试库）。"""
    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("需要 psycopg 才能启用 DATABASE_URL") from exc
    statements = split_statements(convert_schema(schema_sql))
    with psycopg.connect(dsn(), autocommit=True) as conn:
        with conn.cursor() as cursor:
            if reset:
                cursor.execute("DROP SCHEMA public CASCADE")
                cursor.execute("CREATE SCHEMA public")
            for statement in statements:
                cursor.execute(statement)
