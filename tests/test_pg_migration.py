#!/usr/bin/env python
"""SQLite → PostgreSQL 迁移工具测试（不依赖 PG；PG 导入用环境变量可选验证）。"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "server"))
sys.path.insert(0, str(ROOT))

import db  # noqa: E402
import seed  # noqa: E402
from production import migrate_to_pg  # noqa: E402


class PgMigrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="medagent-pg-"))
        cls.db_path = cls.tmp / "app.db"
        conn = db.init_db(cls.db_path, reset=True)
        seed.seed(conn)
        conn.close()
        cls.dump = migrate_to_pg.export_database(cls.db_path)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_01_schema_conversion(self):
        sql = "\n".join(self.dump["schema"])
        self.assertIn("BIGSERIAL PRIMARY KEY", sql)
        self.assertNotIn("AUTOINCREMENT", sql.upper())
        self.assertNotIn("PRAGMA", sql.upper())
        self.assertGreaterEqual(len(self.dump["tables"]), 20)
        self.assertGreater(self.dump["total_rows"], 20)

    def test_02_export_checksums_and_audit_chain(self):
        audit = next(table for table in self.dump["tables"] if table["name"] == "audit_logs")
        self.assertGreaterEqual(audit["rows"], 1)
        row = audit["data"][0]
        self.assertTrue(row["hash"])
        self.assertEqual(len(row["hash"]), 64)
        manifest = migrate_to_pg.write_artifacts(self.dump, self.tmp / "out")
        self.assertEqual(manifest["tables"], len(self.dump["tables"]))
        self.assertEqual(len(manifest["dump_sha256"]), 64)
        self.assertTrue((self.tmp / "out" / "dump.json").is_file())
        self.assertTrue((self.tmp / "out" / "schema.sql").is_file())

    def test_03_cli_export(self):
        out = self.tmp / "cli-out"
        code = migrate_to_pg.main(["--db", str(self.db_path), "--out", str(out)])
        self.assertEqual(code, 0)
        payload = json.loads((out / "dump.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["total_rows"], self.dump["total_rows"])
        self.assertIn("medagent", (out / "manifest.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
