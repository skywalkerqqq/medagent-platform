"""Dify 长尾应用适配（POC）：登记 Dify 应用 → 平台内 blocking 调用 chat/workflow。

- 配置：`DIFY_BASE_URL`（API 根，含 /v1）+ `DIFY_API_KEY`；应用可覆盖 base_url / api_key_env；
- 未配置时返回 400 `dify_not_configured`；上游失败返回 502 并记录失败调用，不伪造成功；
- 调用记录写入 integration_calls（integration=dify），供数据集成页查看。
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime

import common
import db

TIMEOUT = 30.0


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def status(ctx):
    base = _env("DIFY_BASE_URL")
    key = _env("DIFY_API_KEY")
    configured = bool(base and key)
    count = ctx["conn"].execute("SELECT COUNT(*) AS c FROM dify_apps").fetchone()["c"]
    return 200, {"configured": configured, "base_url": base or "", "apps": count,
                 "mode": "live" if configured else "not_configured",
                 "detail": ("DIFY_BASE_URL/DIFY_API_KEY 已配置" if configured
                            else "未配置（可登记应用，运行需配置 DIFY_BASE_URL/API_KEY）")}


def list_apps(ctx):
    common.require(ctx["user"], "model:read", "仅管理/平台审批角色可查看 Dify 应用")
    rows = ctx["conn"].execute("SELECT * FROM dify_apps ORDER BY id DESC").fetchall()
    return 200, {"items": [dict(row) for row in rows]}


def register_app(ctx):
    conn, user, body = ctx["conn"], ctx["user"], ctx["body"]
    common.require(user, "model:read", "仅管理/平台审批角色可登记 Dify 应用")
    name = common.str_field(body.get("name"), "name", required=True)
    base_url = common.str_field(body.get("base_url"), "base_url", default="")
    app_id = common.str_field(body.get("app_id"), "app_id", default="")
    app_type = common.str_field(body.get("app_type"), "app_type", default="chat").lower()
    if app_type not in ("chat", "workflow"):
        raise common.ApiError(400, "validation", "app_type 只能是 chat/workflow")
    api_key_env = common.str_field(body.get("api_key_env"), "api_key_env", default="DIFY_API_KEY")
    code = "DIFY-" + str(conn.execute("SELECT COUNT(*) AS c FROM dify_apps").fetchone()["c"] + 1).zfill(3)
    app_id_row = conn.execute(
        "INSERT INTO dify_apps(code, name, base_url, app_id, app_type, api_key_env, status, created_by, created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (code, name, base_url, app_id, app_type, api_key_env, "registered", user["id"], db.iso()),
    ).lastrowid
    common.audit(conn, user["id"], "登记 Dify 应用", "dify_app", app_id_row, f"{name}（{app_type}）")
    conn.commit()
    return 201, dict(conn.execute("SELECT * FROM dify_apps WHERE id=?", (app_id_row,)).fetchone())


def _config(conn, app) -> dict | None:
    base = _env("DIFY_BASE_URL") or (app["base_url"] or "")
    key_env = app["api_key_env"] or "DIFY_API_KEY"
    key = _env(key_env)
    if not (base and key):
        return None
    base = base.rstrip("/")
    if not base.endswith("/v1"):
        base += "/v1"
    return {"base": base, "key": key}


def _post(cfg, path, payload) -> dict:
    request = urllib.request.Request(
        cfg["base"] + path,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {cfg['key']}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            body = json.loads(response.read().decode("utf-8", "replace") or "{}")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:200]
        raise RuntimeError(f"Dify HTTP {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise RuntimeError(f"Dify 连接失败：{exc}") from exc
    if not isinstance(body, dict):
        raise RuntimeError("Dify 响应格式异常")
    return body


def _extract(app_type: str, body: dict) -> tuple[str, str, int]:
    usage = ((body.get("metadata") or {}).get("usage") or {}) if isinstance(body.get("metadata"), dict) else {}
    tokens = int(usage.get("total_tokens") or 0) or int(usage.get("prompt_tokens") or 0) + int(usage.get("completion_tokens") or 0)
    if app_type == "workflow":
        data = body.get("data") if isinstance(body.get("data"), dict) else {}
        outputs = data.get("outputs") if isinstance(data.get("outputs"), dict) else {}
        state = str(data.get("status") or "").lower()
        if state and state not in ("succeeded", "success", "completed"):
            raise RuntimeError(f"Dify workflow 状态：{state}")
        answer = outputs.get("answer") or outputs.get("text") or outputs.get("result")
        if answer is None:
            answer = json.dumps(outputs, ensure_ascii=False) if outputs else ""
        conversation_id = body.get("conversation_id") or ""
    else:
        answer = body.get("answer") or body.get("response") or ""
        conversation_id = body.get("conversation_id") or ""
    answer = str(answer or "").strip()
    if not answer:
        raise RuntimeError("Dify 未返回回答内容")
    return answer, conversation_id, tokens


def run_app(ctx):
    conn, user = ctx["conn"], ctx["user"]
    common.require(user, "app:trial", "无 Dify 运行权限")
    app = conn.execute("SELECT * FROM dify_apps WHERE id=?", (int(ctx["params"]["id"]),)).fetchone()
    if not app:
        raise common.ApiError(404, "not_found", "Dify 应用不存在")
    query = common.str_field(ctx["body"].get("query"), "query", required=True)
    cfg = _config(conn, app)
    if not cfg:
        raise common.ApiError(400, "dify_not_configured",
                              "Dify 未配置：请设置 DIFY_BASE_URL/DIFY_API_KEY（或应用 base_url/api_key_env）")
    started = datetime.now().astimezone()
    status_text = "failed"
    external_id = ""
    detail = ""
    try:
        if app["app_type"] == "workflow":
            body = _post(cfg, "/workflows/run", {
                "inputs": {"query": query, "input": query},
                "response_mode": "blocking", "user": f"medagent-{user['id']}",
            })
        else:
            body = _post(cfg, "/chat-messages", {
                "inputs": {}, "query": query, "response_mode": "blocking",
                "conversation_id": "", "user": f"medagent-{user['id']}",
            })
        answer, external_id, tokens = _extract(app["app_type"], body)
        status_text = "succeeded"
        detail = f"Dify {app['app_type']} 调用成功，tokens={tokens}"
    except RuntimeError as exc:
        answer = ""
        detail = str(exc)[:300]
        conn.execute(
            "INSERT INTO integration_calls(integration, action, target, status, external_id, detail, created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            ("dify", "run", f"dify:#{app['id']}", status_text, "", detail, db.iso()))
        conn.execute(
            "INSERT INTO safety_events(app_id, run_id, category, severity, action, detail, created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (None, None, "dify_upstream", "medium", "handoff", detail, db.iso()))
        common.audit(conn, user["id"], "调用 Dify 失败", "dify_app", app["id"], detail)
        conn.commit()
        raise common.ApiError(502, "dify_upstream", f"Dify 调用失败：{detail}")
    latency = int((datetime.now().astimezone() - started).total_seconds() * 1000)
    conn.execute(
        "INSERT INTO integration_calls(integration, action, target, status, external_id, detail, created_at) "
        "VALUES (?,?,?,?,?,?,?)",
        ("dify", "run", f"dify:#{app['id']}", status_text, external_id, detail, db.iso()))
    common.audit(conn, user["id"], "调用 Dify 应用", "dify_app", app["id"], f"{len(query)} 字")
    conn.commit()
    return 200, {"ok": True, "answer": answer, "conversation_id": external_id,
                 "app_type": app["app_type"], "latency_ms": latency, "tokens": tokens,
                 "note": "Dify blocking 调用；平台不修改 Dify 源码"}


ROUTES = [
    ("GET", re.compile(r"^/api/integrations/dify/status$"), status),
    ("GET", re.compile(r"^/api/integrations/dify/apps$"), list_apps),
    ("POST", re.compile(r"^/api/integrations/dify/apps$"), register_app),
    ("POST", re.compile(r"^/api/integrations/dify/apps/(?P<id>\d+)/run$"), run_app),
]
