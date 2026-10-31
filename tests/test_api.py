#!/usr/bin/env python
"""MediAgent 中台 v1.1 接口验收测试（零依赖，进程内启动真实服务）。

覆盖：身份/权限、模板、知识审核与检索、试跑引用与安全、评测门禁、
双审批发布/版本快照/回滚/停用、模型降级、BadCase、患者绑定/随访转人工、审计与指标。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "server" / "app.py"
TMP = ROOT / "tests" / ".tmp_medagent"
PORT = 8091
BASE = f"http://127.0.0.1:{PORT}"


def request(method, path, body=None, token=None, headers=None, timeout=20):
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    parts = urllib.parse.urlsplit(path)
    if parts.query:
        path = parts.path + "?" + urllib.parse.quote(parts.query, safe="=&")
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw.decode("utf-8")) if raw else None)
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        return exc.code, (json.loads(raw.decode("utf-8")) if raw else None)


class MediAgentV11Test(unittest.TestCase):
    proc: subprocess.Popen | None = None
    logs: list = []
    tokens: dict[str, str] = {}
    app_id: int = 0

    @classmethod
    def setUpClass(cls):
        shutil.rmtree(TMP, ignore_errors=True)
        TMP.mkdir(parents=True, exist_ok=True)
        out = open(TMP / "server.log", "wb")
        err = open(TMP / "server.err", "wb")
        cls.logs.extend([out, err])
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        cls.proc = subprocess.Popen(
            [sys.executable, str(APP), "--port", str(PORT), "--db", str(TMP / "app.db"), "--reset"],
            cwd=str(ROOT), stdout=out, stderr=err, env=env,
        )
        deadline = time.time() + 30
        while time.time() < deadline:
            if cls.proc.poll() is not None:
                raise AssertionError("服务启动失败：" + (TMP / "server.err").read_text(encoding="utf-8", errors="replace"))
            try:
                status, payload = request("GET", "/api/health", timeout=2)
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

    # ---------------------------------------------------------------- helpers
    def login(self, user: str, password: str = "medagent123") -> str:
        if user in self.tokens:
            return self.tokens[user]
        status, payload = request("POST", "/api/auth/login", {"username": user, "password": password})
        self.assertEqual(status, 200, payload)
        self.tokens[user] = payload["token"]
        return payload["token"]

    def token(self, user: str) -> str:
        return self.login(user)

    # ---------------------------------------------------------------- tests
    def test_01_health_and_auth_required(self):
        status, payload = request("GET", "/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(payload["version"], "1.1.0")
        status, _ = request("GET", "/api/apps")
        self.assertEqual(status, 401)
        # v1.1 §8.1：客户端可控 X-User-Id 不得作为身份凭据
        status, _ = request("GET", "/api/apps", headers={"X-User-Id": "u_admin"})
        self.assertEqual(status, 401)
        status, payload = request("POST", "/api/auth/login", {"username": "u_creator", "password": "wrong"})
        self.assertEqual(status, 401)
        self.assertEqual(payload["error"]["code"], "invalid_credentials")

    def test_02_templates(self):
        token = self.token("u_creator")
        status, payload = request("GET", "/api/templates", token=token)
        self.assertEqual(status, 200)
        keys = {item["key"] for item in payload["items"]}
        self.assertEqual(keys, {"med-knowledge", "med-qc"})
        self.assertTrue(all("eval_threshold" in item for item in payload["items"]))

    def test_03_knowledge_filtering_and_review(self):
        token = self.token("u_knowledge")
        status, docs = request("GET", "/api/knowledge?limit=100", token=token)
        self.assertEqual(status, 200)
        self.assertGreaterEqual(docs["total"], 6)
        # 过期与待审核不得进入检索
        status, hits = request("GET", "/api/knowledge/search?q=医保支付", token=token)
        self.assertEqual(status, 200)
        self.assertEqual(hits["total"], 0)
        status, hits = request("GET", "/api/knowledge/search?q=输血知情同意", token=token)
        self.assertGreaterEqual(hits["total"], 1)
        # 导入 -> 待审核不可检索 -> 审核通过后可检索
        status, created = request("POST", "/api/knowledge", {
            "title": "POC 测试专用知识条目",
            "source": "POC 测试",
            "owner": "知识运营",
            "scope": ["公共"],
            "effective_at": "2026-01-01T00:00:00+08:00",
            "content": "POC 测试专用知识条目：特殊关键词 ZXQ-2026 的处理流程为三步。",
        }, token=token)
        self.assertEqual(status, 201)
        doc_id = created["id"]
        status, hits = request("GET", "/api/knowledge/search?q=ZXQ-2026", token=token)
        self.assertEqual(hits["total"], 0)
        status, _ = request("POST", f"/api/knowledge/{doc_id}/review", {"decision": "approve", "comment": "测试"}, token=token)
        self.assertEqual(status, 200)
        status, hits = request("GET", "/api/knowledge/search?q=ZXQ-2026", token=token)
        self.assertGreaterEqual(hits["total"], 1)

    def test_04_create_app_and_trial(self):
        token = self.token("u_creator")
        status, app = request("POST", "/api/apps", {"name": "POC 心内科知识助手", "template_key": "med-knowledge"}, token=token)
        self.assertEqual(status, 201, app)
        MediAgentV11Test.app_id = app["id"]
        self.assertEqual(app["status"], "draft")
        self.assertEqual(app["config"]["model_policy"], "precise")
        status, trial = request("POST", f"/api/apps/{self.app_id}/trial",
                                {"query": "社区获得性肺炎抗感染治疗原则"}, token=token)
        self.assertEqual(status, 200)
        self.assertGreaterEqual(len(trial["citations"]), 1)
        self.assertIn("不构成诊疗建议", trial["disclaimer"])
        self.assertIn("template_version", trial["versions"])
        self.assertFalse(trial["degraded"])
        status, app = request("GET", f"/api/apps/{self.app_id}", token=token)
        self.assertEqual(app["status"], "testing")

    def test_05_submit_blocked_without_eval(self):
        token = self.token("u_creator")
        status, payload = request("POST", f"/api/apps/{self.app_id}/submit", token=token)
        self.assertEqual(status, 409)
        self.assertEqual(payload["error"]["code"], "release_blocked")
        details = payload["error"]["details"]
        self.assertTrue(any(item["key"] == "eval" and not item["ok"] for item in details))
        # 无评测权限者不能跑评测
        status, _ = request("POST", "/api/eval/run", {"app_id": self.app_id}, token=token)
        self.assertEqual(status, 403)

    def test_06_eval_then_submit(self):
        evaluator = self.token("u_eval")
        status, run = request("POST", "/api/eval/run", {"app_id": self.app_id}, token=evaluator)
        self.assertEqual(status, 200, run)
        self.assertTrue(run["passed"], run)
        self.assertIn("recall", run["metrics"])
        status, run_detail = request("GET", f"/api/eval/runs/{run['run_id']}", token=evaluator)
        self.assertEqual(status, 200)
        self.assertGreaterEqual(len(run_detail["results"]), 5)
        creator = self.token("u_creator")
        status, submitted = request("POST", f"/api/apps/{self.app_id}/submit", token=creator)
        self.assertEqual(status, 200, submitted)
        self.assertEqual(submitted["status"], "pending_dept")

    def test_07_double_approval_publish_and_rollback(self):
        dept = self.token("u_dept")
        status, approvals = request("GET", "/api/approvals?status=pending", token=dept)
        self.assertEqual(status, 200)
        pending = [item for item in approvals["items"] if item["app_id"] == self.app_id]
        self.assertEqual(len(pending), 1)
        status, result = request("POST", f"/api/approvals/{pending[0]['id']}/decide",
                                 {"decision": "approve", "comment": "同意"}, token=dept)
        self.assertEqual(status, 200, result)
        self.assertEqual(result["status"], "pending_platform")
        platform = self.token("u_platform")
        status, approvals = request("GET", "/api/approvals?status=pending", token=platform)
        pending = [item for item in approvals["items"] if item["app_id"] == self.app_id]
        self.assertEqual(len(pending), 1)
        status, result = request("POST", f"/api/approvals/{pending[0]['id']}/decide",
                                 {"decision": "approve", "comment": "平台通过"}, token=platform)
        self.assertEqual(status, 200, result)
        self.assertEqual(result["status"], "published")
        self.assertEqual(result["version"], 1)
        snapshot = result["snapshot"]
        for key in ("config", "template_version", "prompt_version", "model_policy",
                    "knowledge_versions", "eval_run_id", "published_by", "published_at"):
            self.assertIn(key, snapshot)
        status, app = request("GET", f"/api/apps/{self.app_id}", token=platform)
        self.assertEqual(app["status"], "published")
        self.assertEqual(app["current_version"], 1)
        # 回滚（同一版本，验证接口与权限）
        status, rollback = request("POST", f"/api/apps/{self.app_id}/rollback", {"version": 1}, token=platform)
        self.assertEqual(status, 200)
        self.assertEqual(rollback["current_version"], 1)
        # 创建者不能审批/停用
        status, _ = request("POST", f"/api/apps/{self.app_id}/disable", token=self.token("u_creator"))
        self.assertEqual(status, 403)

    def test_08_safety_blocked_output(self):
        knowledge = self.token("u_knowledge")
        status, doc = request("POST", "/api/knowledge", {
            "title": "安全测试专用知识（含禁止表述）",
            "source": "测试",
            "owner": "测试",
            "scope": ["公共"],
            "effective_at": "2026-01-01T00:00:00+08:00",
            "content": "根据本指南，确诊为肺炎后应立即住院治疗，并每日服用药物。",
        }, token=knowledge)
        self.assertEqual(status, 201)
        request("POST", f"/api/knowledge/{doc['id']}/review", {"decision": "approve"}, token=knowledge)
        creator = self.token("u_creator")
        status, app = request("POST", "/api/apps", {"name": "安全测试应用", "template_key": "med-knowledge"}, token=creator)
        self.assertEqual(status, 201)
        status, trial = request("POST", f"/api/apps/{app['id']}/trial",
                                {"query": "确诊为肺炎后如何处理"}, token=creator)
        self.assertEqual(status, 200)
        self.assertTrue(trial["safety"]["blocked"], trial)
        self.assertTrue(trial["degraded"])
        status, check = request("GET", f"/api/apps/{app['id']}/release-check", token=creator)
        self.assertEqual(status, 200)
        safety_item = next(item for item in check["items"] if item["key"] == "safety")
        self.assertFalse(safety_item["ok"])

    def test_09_model_gateway_and_degrade(self):
        admin = self.token("u_admin")
        status, models = request("GET", "/api/models", token=admin)
        self.assertEqual(status, 200)
        self.assertGreaterEqual(len(models["items"]), 3)
        status, policies = request("GET", "/api/model-policies", token=admin)
        self.assertEqual(status, 200)
        self.assertTrue(any(item["key"] == "precise" for item in policies["items"]))
        status, _ = request("PUT", "/api/models/private-llm", {"status": "disabled"}, token=admin)
        self.assertEqual(status, 200)
        status, result = request("POST", "/api/model-policies/precise/test", token=admin)
        self.assertEqual(status, 200)
        self.assertTrue(result["result"]["degraded"], result)
        self.assertEqual(result["result"]["model_key"], "mock-fallback")
        request("PUT", "/api/models/private-llm", {"status": "enabled"}, token=admin)
        status, calls = request("GET", "/api/model-calls?limit=50", token=admin)
        self.assertEqual(status, 200)
        self.assertGreaterEqual(len(calls["items"]), 1)

    def test_10_badcase_lifecycle(self):
        platform = self.token("u_platform")
        status, created = request("POST", "/api/badcases", {
            "app_id": self.app_id, "question": "测试问题", "output": "测试输出",
            "category": "quality", "severity": "medium",
        }, token=platform)
        self.assertEqual(status, 201)
        badcase_id = created["id"]
        status, _ = request("POST", f"/api/badcases/{badcase_id}", {"action": "assign", "assignee": "u_knowledge"}, token=platform)
        self.assertEqual(status, 200)
        status, closed = request("POST", f"/api/badcases/{badcase_id}",
                                 {"action": "close", "resolution": "已修复并回归"}, token=platform)
        self.assertEqual(status, 200)
        self.assertEqual(closed["status"], "closed")
        status, _ = request("POST", "/api/badcases", {"app_id": self.app_id, "question": "x", "output": "y"},
                            token=self.token("u_creator"))
        self.assertEqual(status, 403)

    def test_11_patient_bind_reports_followup_handoff(self):
        patient = self.token("u_patient")
        status, _ = request("GET", "/api/patient/reports", token=patient)
        self.assertEqual(status, 403)
        status, _ = request("POST", "/api/patient/bind", {"patient_ref": "P0001", "verify_code": "000000"}, token=patient)
        self.assertEqual(status, 400)
        status, bound = request("POST", "/api/patient/bind", {"patient_ref": "P0001", "verify_code": "654321"}, token=patient)
        self.assertEqual(status, 200, bound)
        self.assertTrue(bound["bound"])
        status, me = request("GET", "/api/patient/me", token=patient)
        self.assertEqual(status, 200)
        self.assertTrue(me["bound"])
        status, reports = request("GET", "/api/patient/reports", token=patient)
        self.assertEqual(status, 200)
        self.assertEqual(len(reports["items"]), 1)  # 仅 approved_for_patient=1
        status, tasks = request("GET", "/api/patient/followups", token=patient)
        self.assertEqual(status, 200)
        self.assertGreaterEqual(len(tasks["items"]), 1)
        task_id = tasks["items"][0]["id"]
        status, result = request("POST", f"/api/patient/followups/{task_id}/submit",
                                 {"answers": {"symptom": "胸痛伴呼吸困难"}}, token=patient)
        self.assertEqual(status, 200)
        self.assertTrue(result["risk_flag"])
        self.assertTrue(result["handoff"])
        self.assertIn("就医", result["message"])
        admin = self.token("u_admin")
        status, handoffs = request("GET", "/api/handoffs", token=admin)
        self.assertEqual(status, 200)
        self.assertGreaterEqual(len(handoffs["items"]), 1)
        # 撤回授权后不能再取报告
        status, _ = request("POST", "/api/patient/revoke", {"action": "revoke"}, token=patient)
        self.assertEqual(status, 200)
        status, _ = request("GET", "/api/patient/reports", token=patient)
        self.assertEqual(status, 403)

    def test_12_patient_isolation(self):
        patient = self.token("u_patient")
        # 未绑定用户（doctor）不能访问患者接口
        doctor = self.token("u_doctor")
        status, _ = request("GET", "/api/patient/reports", token=doctor)
        self.assertEqual(status, 403)
        status, _ = request("POST", "/api/patient/bind", {"patient_ref": "P0002", "verify_code": "654321"}, token=doctor)
        self.assertEqual(status, 403)

    def test_13_audit_and_metrics(self):
        creator = self.token("u_creator")
        status, _ = request("GET", "/api/audit?limit=10", token=creator)
        self.assertEqual(status, 403)
        admin = self.token("u_admin")
        status, audit = request("GET", "/api/audit?limit=100", token=admin)
        self.assertEqual(status, 200)
        actions = {item["action"] for item in audit["items"]}
        for action in ("登录", "创建应用", "提交发布", "执行评测", "患者绑定"):
            self.assertIn(action, actions)
        status, exported = request("GET", "/api/audit/export", token=admin)
        self.assertEqual(status, 200)
        self.assertGreater(exported["exported"], 0)
        status, dash = request("GET", "/api/dashboard", token=admin)
        self.assertEqual(status, 200)
        self.assertEqual(len(dash["release_checklist"]), 10)
        status, metrics = request("GET", "/api/ops/metrics", token=admin)
        self.assertEqual(status, 200)
        self.assertGreaterEqual(len(metrics["definitions"]), 8)
        self.assertIn("eval_pass_rate", metrics["values"])

    def test_14_knowledge_permissions(self):
        creator = self.token("u_creator")
        status, _ = request("POST", "/api/knowledge", {
            "title": "无权限", "source": "x", "owner": "x",
            "effective_at": "2026-01-01T00:00:00+08:00", "content": "x",
        }, token=creator)
        self.assertEqual(status, 403)
        status, _ = request("POST", "/api/knowledge/1/review", {"decision": "approve"}, token=creator)
        self.assertEqual(status, 403)

    def test_15_app_validation_and_department(self):
        creator = self.token("u_creator")
        status, _ = request("POST", "/api/apps", {"name": "x", "template_key": "no-such"}, token=creator)
        self.assertEqual(status, 400)
        status, _ = request("POST", "/api/apps", {"name": "x", "template_key": "med-knowledge",
                                                 "department": "财务部"}, token=creator)
        self.assertEqual(status, 403)

    def test_16_approval_permissions(self):
        creator = self.token("u_creator")
        status, _ = request("GET", "/api/approvals", token=creator)
        self.assertEqual(status, 403)
        doctor = self.token("u_doctor")
        status, trial = request("POST", f"/api/apps/{self.app_id}/trial", {"query": "华法林 INR 监测"}, token=doctor)
        self.assertEqual(status, 200)
        self.assertGreaterEqual(len(trial["trace"]), 3)
        self.assertTrue(any(step["type"] == "model" for step in trial["trace"]))
        status, feedback = request("POST", f"/api/apps/{self.app_id}/feedback", {
            "helpful": False, "question": "华法林 INR 监测", "output": trial["output"],
            "reason": "accuracy", "comment": "缺少监测频率",
        }, token=doctor)
        self.assertEqual(status, 200)
        self.assertIsNotNone(feedback["badcase_id"])

    def test_17_disable_app(self):
        platform = self.token("u_platform")
        status, result = request("POST", f"/api/apps/{self.app_id}/disable", token=platform)
        self.assertEqual(status, 200)
        self.assertEqual(result["status"], "disabled")
        status, app = request("GET", f"/api/apps/{self.app_id}", token=platform)
        self.assertEqual(app["status"], "disabled")

    def test_19_wx_login_patient_flow(self):
        # 未登录可调用微信登录（dev mock，POC 演示）
        status, data = request("POST", "/api/auth/wx-login", {"code": "mock-code-001"})
        self.assertEqual(status, 200, data)
        self.assertEqual(data["mode"], "mock")
        self.assertEqual(data["user"]["role"], "patient")
        wx_token = data["token"]
        status, _ = request("GET", "/api/patient/reports", token=wx_token)
        self.assertEqual(status, 403)  # 微信身份不等于医疗身份
        status, bound = request("POST", "/api/patient/bind",
                                {"patient_ref": "P0002", "verify_code": "654321"}, token=wx_token)
        self.assertEqual(status, 200, bound)
        status, reports = request("GET", "/api/patient/reports", token=wx_token)
        self.assertEqual(status, 200)
        self.assertGreaterEqual(len(reports["items"]), 1)
        admin = self.token("u_admin")
        status, audit = request("GET", "/api/audit?limit=100", token=admin)
        self.assertIn("微信登录", {item["action"] for item in audit["items"]})

    def test_20_server_stable(self):
        status, payload = request("GET", "/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "ok")

    def test_21_memory_crud_and_injection(self):
        creator = self.token("u_creator")
        status, memories = request("GET", "/api/memories?limit=100", token=creator)
        self.assertEqual(status, 200)
        self.assertGreaterEqual(memories["stats"]["active"], 3)
        status, created = request("POST", "/api/memories", {
            "scope": "user", "type": "preference", "content": "我偏好先看结论，再看引用依据。",
            "importance": 2,
        }, token=creator)
        self.assertEqual(status, 201, created)
        self.assertTrue(str(created["owner"]) == "u_creator")
        status, deduped = request("POST", "/api/memories", {
            "scope": "user", "type": "preference", "content": "我偏好先看结论，再看引用依据。",
            "importance": 3,
        }, token=creator)
        self.assertEqual(status, 200)
        self.assertTrue(deduped["deduped"])
        memory_id = created["id"]
        status, updated = request("PUT", f"/api/memories/{memory_id}", {"status": "deleted"}, token=creator)
        self.assertEqual(status, 200)
        self.assertEqual(updated["status"], "deleted")
        # 注入：app1 已开启 memory_enabled；医生用户记忆命中“抗感染”
        doctor = self.token("u_doctor")
        status, mem = request("POST", "/api/memories", {
            "scope": "user", "type": "fact", "content": "抗感染治疗需关注疗程与耐药风险。",
            "importance": 3,
        }, token=doctor)
        self.assertEqual(status, 201)
        status, trial = request("POST", "/api/apps/1/trial",
                                {"query": "社区获得性肺炎抗感染治疗原则"}, token=doctor)
        self.assertEqual(status, 200)
        self.assertTrue(trial["memory"]["enabled"])
        self.assertGreaterEqual(trial["memory"]["injected"], 1)
        self.assertIn("结合历史记忆", trial["output"])
        self.assertTrue(any(step["type"] == "memory" for step in trial["trace"]))
        # 患者无记忆权限；硬删除仅管理员
        patient = self.token("u_patient")
        status, _ = request("GET", "/api/memories", token=patient)
        self.assertEqual(status, 403)
        admin = self.token("u_admin")
        status, hard = request("DELETE", f"/api/memories/{memory_id}?hard=1", token=admin)
        self.assertEqual(status, 200)
        self.assertTrue(hard["hard"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
