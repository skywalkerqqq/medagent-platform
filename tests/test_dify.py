#!/usr/bin/env python
"""Dify 长尾适配集成测试：fake Dify + 平台内 blocking 调用 chat/workflow。"""
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
TMP = ROOT / "tests" / ".tmp_dify"
PORT = 8093
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


class FakeDify:
    def __init__(self):
        self.calls = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                return

            def _send(self, status, payload):
                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                length = int(self.headers.get("Content-Length") or 0)
                payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
                outer.calls.append(payload)
                text = json.dumps(payload, ensure_ascii=False)
                if "错误" in text:
                    self._send(500, {"error": "fake dify error"})
                    return
                if self.path.endswith("/chat-messages"):
                    self._send(200, {"answer": "DIFY-CHAT-ANSWER：平台内 Dify 调用成功",
                                     "conversation_id": "conv-1",
                                     "metadata": {"usage": {"prompt_tokens": 10, "completion_tokens": 20}}})
                elif self.path.endswith("/workflows/run"):
                    self._send(200, {"data": {"status": "succeeded",
                                              "outputs": {"answer": "DIFY-WORKFLOW-ANSWER：工作流输出"}},
                                     "conversation_id": "conv-wf"})
                else:
                    self._send(404, {"error": "not found"})

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def stop(self):
        self.server.shutdown()
        self.server.server_close()


class DifyAdapterTest(unittest.TestCase):
    proc = None
    fake = None
    logs = []

    @classmethod
    def setUpClass(cls):
        cls.fake = FakeDify()
        shutil.rmtree(TMP, ignore_errors=True)
        TMP.mkdir(parents=True, exist_ok=True)
        out = open(TMP / "server.log", "wb")
        err = open(TMP / "server.err", "wb")
        cls.logs.extend([out, err])
        env = os.environ.copy()
        env.update({
            "PYTHONIOENCODING": "utf-8",
            "DIFY_BASE_URL": cls.fake.base + "/v1",
            "DIFY_API_KEY": "fake-dify-key",
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

    def test_01_status_and_seed_app(self):
        token = self.login()
        status, health = request("GET", "/api/integrations/dify/status", token=token)
        self.assertEqual(status, 200)
        self.assertTrue(health["configured"])
        status, apps = request("GET", "/api/integrations/dify/apps", token=token)
        self.assertEqual(status, 200)
        self.assertGreaterEqual(len(apps["items"]), 1)

    def test_02_chat_and_workflow_run(self):
        token = self.login()
        status, chat = request("POST", "/api/integrations/dify/apps", {
            "name": "Dify Chat 测试", "base_url": self.fake.base, "app_id": "app-chat",
            "app_type": "chat",
        }, token=token)
        self.assertEqual(status, 201, chat)
        status, result = request("POST", f"/api/integrations/dify/apps/{chat['id']}/run",
                                 {"query": "写一段营销文案"}, token=token)
        self.assertEqual(status, 200, result)
        self.assertIn("DIFY-CHAT-ANSWER", result["answer"])
        self.assertGreater(result["tokens"], 0)
        status, workflow = request("POST", "/api/integrations/dify/apps", {
            "name": "Dify Workflow 测试", "base_url": self.fake.base, "app_id": "app-wf",
            "app_type": "workflow",
        }, token=token)
        self.assertEqual(status, 201, workflow)
        status, result = request("POST", f"/api/integrations/dify/apps/{workflow['id']}/run",
                                 {"query": "整理会议纪要"}, token=token)
        self.assertEqual(status, 200, result)
        self.assertIn("DIFY-WORKFLOW-ANSWER", result["answer"])

    def test_03_upstream_failure_not_faked(self):
        token = self.login()
        status, app = request("POST", "/api/integrations/dify/apps", {
            "name": "Dify 失败测试", "base_url": self.fake.base, "app_type": "chat",
        }, token=token)
        self.assertEqual(status, 201)
        status, error = request("POST", f"/api/integrations/dify/apps/{app['id']}/run",
                                {"query": "触发错误"}, token=token)
        self.assertEqual(status, 502)
        self.assertEqual(error["error"]["code"], "dify_upstream")
        status, calls = request("GET", "/api/integrations/calls", token=token)
        self.assertTrue(any(call["integration"] == "dify" and call["status"] == "failed"
                            for call in calls["items"]))

    def test_04_health_stable(self):
        status, payload = request("GET", "/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "ok")


if __name__ == "__main__":
    unittest.main(verbosity=2)
