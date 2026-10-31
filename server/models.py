"""模型网关：模型注册、策略路由、降级标记、真实上游（OpenAI 兼容）与调用记录。"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request

import common
import db


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def live_config() -> dict | None:
    """LLM_MODE=live 时启用真实上游（OpenAI 兼容）。"""
    if _env("LLM_MODE").lower() != "live":
        return None
    base = _env("LLM_BASE_URL").rstrip("/")
    key = _env("LLM_API_KEY")
    model = _env("LLM_MODEL")
    if not (base and key and model):
        return None
    return {"base": base, "key": key, "model": model}


def _live_chat(prompt: str, timeout_ms: int = 20000) -> tuple[str, int, int]:
    """调用 OpenAI 兼容 /chat/completions，返回 (text, tokens_in, tokens_out)。"""
    cfg = live_config()
    if not cfg:
        raise RuntimeError("live_not_configured")
    url = cfg["base"] + ("/chat/completions" if cfg["base"].endswith("/v1") else "/v1/chat/completions")
    payload = {
        "model": cfg["model"],
        "temperature": 0.1,
        "messages": [
            {"role": "system", "content": "你是医疗 AI 辅助工具。只依据提供的资料回答，必须保留引用编号，"
                                          "不给出诊断结论、处方或剂量；无依据时明确说明未找到依据。"},
            {"role": "user", "content": prompt},
        ],
    }
    request = urllib.request.Request(
        url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {cfg['key']}"},
    )
    started = time.time()
    try:
        with urllib.request.urlopen(request, timeout=max(5, timeout_ms / 1000)) as response:
            body = json.loads(response.read().decode("utf-8", "replace") or "{}")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, OSError) as exc:
        raise RuntimeError(f"live_upstream_error: {exc}") from exc
    choices = body.get("choices") if isinstance(body, dict) else None
    if not choices:
        raise RuntimeError("live_empty_choices")
    message = choices[0].get("message") or {}
    text = str(message.get("content") or "").strip()
    if not text:
        raise RuntimeError("live_empty_content")
    usage = body.get("usage") or {}
    return text, int(usage.get("prompt_tokens") or 0), int(usage.get("completion_tokens") or 0)


def list_models(ctx):
    common.require(ctx["user"], "model:read")
    rows = ctx["conn"].execute("SELECT * FROM models ORDER BY is_private DESC, key").fetchall()
    return 200, {"items": [dict(row) for row in rows]}


def list_policies(ctx):
    common.require(ctx["user"], "model:read")
    rows = ctx["conn"].execute("SELECT * FROM model_policies ORDER BY key").fetchall()
    items = []
    for row in rows:
        item = dict(row)
        item["chain"] = common.loads(item["chain"], [])
        items.append(item)
    return 200, {"items": items}


def call_gateway(conn, app_id, policy_key: str, prompt: str, generate: bool = False) -> dict:
    """按策略链选择模型；主模型不可用时降级并显式标记。

    generate=True 且 LLM_MODE=live 时调用真实 OpenAI 兼容上游；失败时返回 ok=False，
    由调用方回退模板回答并标记降级，不把失败当成功。
    """
    policy = conn.execute("SELECT * FROM model_policies WHERE key=?", (policy_key,)).fetchone()
    if not policy:
        return {"ok": False, "error_code": "policy_not_found", "degraded": True, "policy": policy_key}
    chain = common.loads(policy["chain"], []) or []
    chosen = None
    degraded = False
    for index, model_key in enumerate(chain):
        model = conn.execute("SELECT * FROM models WHERE key=?", (model_key,)).fetchone()
        if model and model["status"] == "enabled":
            chosen = model
            degraded = index > 0
            break
    if not chosen:
        conn.execute(
            "INSERT INTO model_calls(app_id, policy, model_key, degraded, latency_ms, tokens, cost, error_code, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (app_id, policy_key, "", 1, 0, 0, 0, "model_unavailable", db.iso()),
        )
        conn.commit()
        return {"ok": False, "error_code": "model_unavailable", "degraded": True, "policy": policy_key}
    cfg = live_config()
    use_live = bool(generate and cfg and chosen["provider"] == "openai_compatible")
    if use_live:
        started = time.time()
        try:
            text, tokens_in, tokens_out = _live_chat(prompt, int(chosen["timeout_ms"] or 20000))
        except RuntimeError as exc:
            latency = int((time.time() - started) * 1000)
            conn.execute(
                "INSERT INTO model_calls(app_id, policy, model_key, degraded, latency_ms, tokens, cost, error_code, created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (app_id, policy_key, chosen["key"], 1, latency, 0, 0, str(exc)[:180], db.iso()),
            )
            conn.commit()
            return {"ok": False, "error_code": "live_failed", "detail": str(exc)[:200],
                    "degraded": True, "policy": policy_key, "model_key": chosen["key"],
                    "live": True, "latency_ms": latency}
        latency = max(1, int((time.time() - started) * 1000))
        tokens = tokens_in + tokens_out
        cost = round(tokens * 0.002 / 1000, 6)
        conn.execute(
            "INSERT INTO model_calls(app_id, policy, model_key, degraded, latency_ms, tokens, cost, error_code, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (app_id, policy_key, chosen["key"], 1 if degraded else 0, latency, tokens, cost, "", db.iso()),
        )
        return {
            "ok": True, "policy": policy_key, "model_key": chosen["key"],
            "model_name": chosen["name"], "degraded": degraded,
            "latency_ms": latency, "tokens": tokens, "cost": cost,
            "error_code": "", "live": True, "text": text,
        }
    digest = int(hashlib.md5((prompt or "").encode("utf-8")).hexdigest()[:8], 16)
    latency = 120 + digest % 280
    tokens = max(40, len(prompt or "") // 2 + 60)
    cost = round(tokens * 0.002 / 1000, 6)
    conn.execute(
        "INSERT INTO model_calls(app_id, policy, model_key, degraded, latency_ms, tokens, cost, error_code, created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (app_id, policy_key, chosen["key"], 1 if degraded else 0, latency, tokens, cost, "", db.iso()),
    )
    return {
        "ok": True,
        "policy": policy_key,
        "model_key": chosen["key"],
        "model_name": chosen["name"],
        "degraded": degraded,
        "latency_ms": latency,
        "tokens": tokens,
        "cost": cost,
        "error_code": "",
        "live": False,
        "text": None,
    }


def test_policy(ctx):
    common.require(ctx["user"], "model:read", "仅管理/平台审批角色可测试模型策略")
    key = ctx["params"]["key"]
    result = call_gateway(ctx["conn"], None, key, "模型网关连通性测试")
    ctx["conn"].commit()
    if not result["ok"]:
        return 200, {"ok": False, "result": result, "note": "模型不可用；按故障安全要求应转人工，不得伪造模型结果"}
    return 200, {"ok": True, "result": result}


def update_model(ctx):
    conn, user, body = ctx["conn"], ctx["user"], ctx["body"]
    common.require(user, "model:write", "仅管理员可变更模型状态")
    key = ctx["params"]["key"]
    row = conn.execute("SELECT * FROM models WHERE key=?", (key,)).fetchone()
    if not row:
        raise common.ApiError(404, "not_found", "模型不存在")
    status = common.str_field(body.get("status"), "status", default=row["status"])
    if status not in ("enabled", "disabled"):
        raise common.ApiError(400, "validation", "status 只能是 enabled/disabled")
    conn.execute("UPDATE models SET status=? WHERE key=?", (status, key))
    common.audit(conn, user["id"], "变更模型状态", "model", key, status)
    conn.commit()
    return 200, dict(conn.execute("SELECT * FROM models WHERE key=?", (key,)).fetchone())


def list_calls(ctx):
    common.require(ctx["user"], "model:read")
    limit, offset = common.pagination(ctx["query"])
    rows = ctx["conn"].execute(
        "SELECT * FROM model_calls ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset)
    ).fetchall()
    return 200, {"items": [dict(row) for row in rows]}


ROUTES = [
    ("GET", re.compile(r"^/api/models$"), list_models),
    ("PUT", re.compile(r"^/api/models/(?P<key>[a-z0-9-]+)$"), update_model),
    ("GET", re.compile(r"^/api/model-policies$"), list_policies),
    ("POST", re.compile(r"^/api/model-policies/(?P<key>[a-z0-9-]+)/test$"), test_policy),
    ("GET", re.compile(r"^/api/model-calls$"), list_calls),
]
