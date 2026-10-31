#!/usr/bin/env python
"""限流与安全响应头测试（stdlib 服务，独立端口/低阈值）。"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "server" / "app.py"
TMP = ROOT / "tests" / ".tmp_rate"
PORT = 8096
BASE = f"http://127.0.0.1:{PORT}"


def request(method, path, body=None, token=None):
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw.decode("utf-8")) if raw else None), dict(resp.headers)
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        return exc.code, (json.loads(raw.decode("utf-8")) if raw else None), dict(exc.headers)


class RateLimitTest(unittest.TestCase):
    proc = None

    @classmethod
    def setUpClass(cls):
        shutil.rmtree(TMP, ignore_errors=True)
        TMP.mkdir(parents=True, exist_ok=True)
        out = open(TMP / "server.log", "wb")
        err = open(TMP / "server.err", "wb")
        cls.logs = [out, err]
        env = os.environ.copy()
        env.update({"PYTHONIOENCODING": "utf-8", "RATE_LIMIT_RPS": "1", "RATE_LIMIT_BURST": "3"})
        cls.proc = subprocess.Popen(
            [sys.executable, str(APP), "--port", str(PORT), "--db", str(TMP / "app.db"), "--reset"],
            cwd=str(ROOT), stdout=out, stderr=err, env=env,
        )
        deadline = time.time() + 30
        while time.time() < deadline:
            if cls.proc.poll() is not None:
                raise AssertionError((TMP / "server.err").read_text(encoding="utf-8", errors="replace"))
            try:
                status, _, _ = request("GET", "/api/health")
                if status == 200:
                    return
            except Exception:
                pass
            time.sleep(0.1)
        raise AssertionError("服务未就绪")

    @classmethod
    def tearDownClass(cls):
        if cls.proc and cls.proc.poll() is None:
            cls.proc.terminate()
            try:
                cls.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                cls.proc.kill()
        for handle in cls.logs:
            try:
                handle.close()
            except OSError:
                pass
        shutil.rmtree(TMP, ignore_errors=True)

    def login(self):
        status, payload, headers = request("POST", "/api/auth/login",
                                           {"username": "u_admin", "password": "medagent123"})
        self.assertEqual(status, 200, payload)
        self.assertEqual(headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(headers.get("X-Frame-Options"), "DENY")
        return payload["token"]

    def test_01_rate_limited_and_retry_after(self):
        token = self.login()
        statuses = []
        retry_after = None
        limited = None
        for _ in range(8):
            status, payload, headers = request("GET", "/api/apps", token=token)
            statuses.append(status)
            if status == 429:
                limited = payload
                retry_after = headers.get("Retry-After")
                break
        self.assertIn(429, statuses, statuses)
        self.assertEqual(limited["error"]["code"], "rate_limited")
        self.assertIsNotNone(retry_after)
        # 健康检查不参与限流，仍应可用
        status, _, _ = request("GET", "/api/health")
        self.assertEqual(status, 200)

    def test_02_health_stable(self):
        status, payload, _ = request("GET", "/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "ok")


if __name__ == "__main__":
    unittest.main(verbosity=2)
