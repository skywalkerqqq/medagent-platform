#!/usr/bin/env python
"""真实模型上游（OpenAI 兼容）集成测试：LLM_MODE=live + fake /chat/completions。"""
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
TMP = ROOT / "tests" / ".tmp_llm_live"
PORT = 8092
BASE = f"http://127.0.0.1:{PORT}"


def request(method, path, body=None, token=None, timeout=30):
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


class FakeLLM:
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
                text = json.dumps(payload, ensure_ascii=False)
                outer.calls.append({"path": self.path, "payload": payload})
                if "触发失败" in text:
                    self._send(500, {"error": "fake upstream error"})
                    return
                self._send(200, {
                    "choices": [{"message": {"role": "assistant",
                                             "content": "LIVE-ANSWER：根据院内资料，建议结合临床评估（引用保留）。"}}],
                    "usage": {"prompt_tokens": 21, "completion_tokens": 34},
                })

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def stop(self):
        self.server.shutdown()
        self.server.server_close()


class MediAgentLiveLLMTest(unittest.TestCase):
    proc = None
    fake = None
    logs = []

    @classmethod
    def setUpClass(cls):
        cls.fake = FakeLLM()
        shutil.rmtree(TMP, ignore_errors=True)
        TMP.mkdir(parents=True, exist_ok=True)
        out = open(TMP / "server.log", "wb")
        err = open(TMP / "server.err", "wb")
        cls.logs.extend([out, err])
        env = os.environ.copy()
        env.update({
            "PYTHONIOENCODING": "utf-8",
            "LLM_MODE": "live",
            "LLM_BASE_URL": cls.fake.base + "/v1",
            "LLM_API_KEY": "fake-key",
            "LLM_MODEL": "fake-model",
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

    def login(self, user="u_doctor"):
        status, payload = request("POST", "/api/auth/login",
                                  {"username": user, "password": "medagent123"})
        self.assertEqual(status, 200, payload)
        return payload["token"]

    def test_01_live_answer_used(self):
        token = self.login()
        status, trial = request("POST", "/api/apps/1/trial",
                                {"query": "社区获得性肺炎抗感染治疗原则"}, token=token)
        self.assertEqual(status, 200, trial)
        self.assertIn("LIVE-ANSWER", trial["output"])
        self.assertFalse(trial["degraded"], trial)
        self.assertTrue(self.fake.calls, "应调用真实上游")
        model_step = next(step for step in trial["trace"] if step["type"] == "model")
        self.assertIn("真实上游", model_step["detail"])
        self.assertGreater(trial["tokens"], 0)

    def test_02_live_failure_falls_back_safely(self):
        token = self.login()
        status, trial = request("POST", "/api/apps/1/trial",
                                {"query": "触发失败：请给出治疗方案"}, token=token)
        self.assertEqual(status, 200, trial)
        self.assertNotIn("LIVE-ANSWER", trial["output"])
        self.assertTrue(trial["degraded"], trial)
        self.assertIn("模型服务当前不可用", trial["output"])

    def test_03_health_stable(self):
        status, payload = request("GET", "/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "ok")


if __name__ == "__main__":
    unittest.main(verbosity=2)
