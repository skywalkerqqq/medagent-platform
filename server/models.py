"""模型网关：模型注册、策略路由、降级标记与调用记录。"""
from __future__ import annotations

import hashlib
import re

import common
import db


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


def call_gateway(conn, app_id, policy_key: str, prompt: str) -> dict:
    """按策略链选择模型；主模型不可用时降级并显式标记。"""
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
