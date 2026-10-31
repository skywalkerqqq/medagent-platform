#!/usr/bin/env python
"""告警通知渠道集成测试：fake 企业微信/钉钉 webhook。"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "server" / "app.py"
TMP = ROOT / "tests" / ".tmp_notify"
PORT = 8095
BASE = f"http://127.0.0.1:{PORT}"


def request(method, path, body=None, token=None, timeout=20):
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw.decode("utf-8")) if raw else None)
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        return exc.code, (json.loads(raw.decode("utf-8")) if raw else None)


class FakeWebhook:
    def __init__(self):
        self.calls = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                return

            def do_POST(self):
                length = int(self.headers.get("Content-Length") or 0)
                payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
                outer.calls.append({"path": self.path, "payload": payload})
                if self.path == "/bad":
                    self.send_response(500)
                    self.end_headers()
                    self.wfile.write(b"webhook failure")
                    return
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"errcode":0}')

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def stop(self):
        self.server.shutdown()
        self.server.server_close()


class NotifyTest(unittest.TestCase):
    proc = None
    fake = None
    logs = []

    @classmethod
    def setUpClass(cls):
        cls.fake = FakeWebhook()
        shutil.rmtree(TMP, ignore_errors=True)
        TMP.mkdir(parents=True, exist_ok=True)
        out = open(TMP / "server.log", "wb")
        err = open(TMP / "server.err", "wb")
        cls.logs.extend([out, err])
        env = os.environ.copy()
        env.update({
            "PYTHONIOENCODING": "utf-8",
            "ALERT_WEBHOOK_URL": cls.fake.base + "/ok",
            "BAD_WEBHOOK_URL": cls.fake.base + "/bad",
        })
        cls.proc = subprocess.Popen(
            [sys.executable, str(APP), "--port", str(PORT), "--db", str(TMP / "app.db"), "--reset"],
            cwd=str(ROOT), stdout=out, stderr=err, env=env,
        )
        deadline = time.time() + 30
        while time.time() < deadline:
            if cls.proc.poll() is not None:
                raise AssertionError((TMP / "server.err").read_text(encoding="utf-8", errors="replace"))
            try:
                status, _ = request("GET", "/api/health", timeout=2)
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
        if cls.fake:
            cls.fake.stop()
        shutil.rmtree(TMP, ignore_errors=True)

    def login(self, user="u_admin"):
        status, payload = request("POST", "/api/auth/login",
                                  {"username": user, "password": "medagent123"})
        self.assertEqual(status, 200, payload)
        return payload["token"]

    def test_01_seed_channel_configured(self):
        token = self.login()
        status, channels = request("GET", "/api/ops/notify/channels", token=token)
        self.assertEqual(status, 200)
        self.assertGreaterEqual(len(channels["items"]), 1)
        seed = channels["items"][0]
        self.assertTrue(seed["configured"])
        status, _ = request("GET", "/api/ops/notify/channels", token=self.login("u_patient"))
        self.assertEqual(status, 403)

    def test_02_test_send_and_alert_notify(self):
        token = self.login()
        status, channels = request("GET", "/api/ops/notify/channels", token=token)
        channel_id = channels["items"][0]["id"]
        before = len(self.fake.calls)
        status, result = request("POST", f"/api/ops/notify/channels/{channel_id}/test", token=token)
        self.assertEqual(status, 200, result)
        self.assertEqual(result["status"], "sent")
        self.assertGreater(len(self.fake.calls), before)
        self.assertIn("MediAgent", json.dumps(self.fake.calls[-1]["payload"], ensure_ascii=False))
        self.assertEqual(self.fake.calls[-1]["payload"]["msgtype"], "text")
        status, result = request("POST", "/api/ops/alerts/notify", token=token)
        self.assertEqual(status, 200, result)
        self.assertGreaterEqual(len(result["sent"]), 1)
        text = json.dumps(self.fake.calls[-1]["payload"], ensure_ascii=False)
        self.assertIn("运营告警", text)

    def test_03_upstream_failure_not_faked(self):
        token = self.login()
        status, channel = request("POST", "/api/ops/notify/channels", {
            "name": "失败渠道", "kind": "wecom", "webhook_env": "BAD_WEBHOOK_URL",
        }, token=token)
        self.assertEqual(status, 201, channel)
        status, error = request("POST", f"/api/ops/notify/channels/{channel['id']}/test", token=token)
        self.assertEqual(status, 502)
        self.assertEqual(error["error"]["code"], "notify_upstream")
        status, calls = request("GET", "/api/integrations/calls", token=token)
        self.assertTrue(any(call["integration"] == "notify" and call["status"] == "failed"
                            for call in calls["items"]))

    def test_04_health_stable(self):
        status, payload = request("GET", "/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "ok")


if __name__ == "__main__":
    unittest.main(verbosity=2)
