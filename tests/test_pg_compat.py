#!/usr/bin/env python
"""PostgreSQL 运行时兼容层测试：纯转换逻辑 + 可选真实 PG 烟测。

真实 PG 烟测需要：
  $env:PG_TEST_URL="postgresql://user:pass@host:5432/medagent_test"
  $env:PG_TEST_ALLOW_RESET="1"   # 会 DROP public schema，仅专用测试库！
否则自动跳过。
"""
from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "server"))

import pg_compat  # noqa: E402

HAS_PSYCOPG = importlib.util.find_spec("psycopg") is not None
PG_URL = os.environ.get("PG_TEST_URL", "")
PG_RESET = os.environ.get("PG_TEST_ALLOW_RESET", "") in ("1", "true", "yes")


class PgCompatPureTest(unittest.TestCase):
    def test_01_placeholders_skip_literals(self):
        sql = "SELECT * FROM apps WHERE id=? AND note='? literal' AND name=?"
        self.assertEqual(pg_compat.convert_placeholders(sql),
                         "SELECT * FROM apps WHERE id=%s AND note='? literal' AND name=%s")

    def test_02_insert_lastrowid_compat(self):
        prepared, returning = pg_compat.prepare_sql(
            "INSERT INTO apps(code, name) VALUES (?,?)", {"apps"})
        self.assertIn("RETURNING id", prepared)
        self.assertTrue(returning)
        self.assertIn("%s", prepared)
        prepared, returning = pg_compat.prepare_sql(
            "INSERT INTO institutions(id, name) VALUES (?,?)", {"apps"})
        self.assertFalse(returning)
        self.assertNotIn("RETURNING", prepared)

    def test_03_insert_or_ignore(self):
        prepared, _ = pg_compat.prepare_sql(
            "INSERT OR IGNORE INTO institutions(id, name) VALUES (?,?)", set())
        self.assertTrue(prepared.startswith("INSERT INTO"))
        self.assertIn("ON CONFLICT DO NOTHING", prepared)
        self.assertNotIn("OR IGNORE", prepared)

    def test_04_schema_conversion(self):
        schema = pg_compat.convert_schema(
            "CREATE TABLE x (id INTEGER PRIMARY KEY AUTOINCREMENT, amount REAL, at DATETIME);")
        self.assertIn("BIGSERIAL PRIMARY KEY", schema)
        self.assertIn("DOUBLE PRECISION", schema)
        self.assertIn("TIMESTAMPTZ", schema)
        self.assertNotIn("AUTOINCREMENT", schema.upper())

    def test_05_row_compatibility(self):
        row = pg_compat.PGRow(["id", "name"], (1, "测试"))
        self.assertEqual(row[0], 1)
        self.assertEqual(row["name"], "测试")
        self.assertEqual(dict(row), {"id": 1, "name": "测试"})
        self.assertEqual(list(row.keys()), ["id", "name"])

    def test_06_split_statements(self):
        statements = pg_compat.split_statements("CREATE TABLE a(id INT); CREATE INDEX i ON a(id);")
        self.assertEqual(len(statements), 2)


@unittest.skipUnless(HAS_PSYCOPG and PG_URL and PG_RESET,
                     "需要 psycopg + PG_TEST_URL + PG_TEST_ALLOW_RESET=1（会 DROP public schema）")
class PgRuntimeSmokeTest(unittest.TestCase):
    def test_runtime_init_seed_and_query(self):
        import db
        import seed
        import common

        os.environ["DATABASE_URL"] = PG_URL
        try:
            conn = db.init_db(Path(tempfile.mkdtemp(prefix="medagent-pg-rt-")) / "unused.db", reset=True)
            try:
                seed.seed(conn)
                user = conn.execute("SELECT id, role FROM users WHERE id=?", ("u_admin",)).fetchone()
                self.assertEqual(user["role"], "admin")
                common.audit(conn, "u_admin", "PG 烟测", "system", "", "runtime compat")
                conn.commit()
                audit = conn.execute("SELECT hash FROM audit_logs ORDER BY id DESC LIMIT 1").fetchone()
                self.assertEqual(len(audit["hash"]), 64)
                app = conn.execute("SELECT id FROM apps ORDER BY id LIMIT 1").fetchone()
                self.assertGreaterEqual(app[0], 1)
            finally:
                conn.close()
        finally:
            os.environ.pop("DATABASE_URL", None)


if __name__ == "__main__":
    unittest.main(verbosity=2)
