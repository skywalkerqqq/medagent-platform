"""运营告警通知渠道（企业微信/钉钉/generic webhook）。

- 渠道只保存 `webhook_env` 环境变量名，密钥不进数据库/前端；
- 发送走 POST JSON；未配置返回 400 `notify_not_configured`，上游失败 502 `notify_upstream` 并记录失败调用；
- 所有测试/告警发送写 integration_calls（integration=notify）与审计。
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request

import common
import db
import ops

TIMEOUT = 10


def _env(name: str) -> str:
    return (os.environ.get(name) or "").strip()


def _channel_json(row) -> dict:
    data = dict(row)
    data["configured"] = bool(_env(data["webhook_env"] or ""))
    data["webhook_masked"] = "已配置（环境变量）" if data["configured"] else "未配置"
    return data


def list_channels(ctx):
    common.require(ctx["user"], "metrics:read")
    rows = ctx["conn"].execute("SELECT * FROM notify_channels ORDER BY id").fetchall()
    return 200, {"items": [_channel_json(row) for row in rows],
                 "note": "webhook 地址仅从环境变量读取，不在接口/页面展示；未配置渠道不会发送。"}


def create_channel(ctx):
    conn, user, body = ctx["conn"], ctx["user"], ctx["body"]
    common.require(user, "model:read", "仅管理/平台审批角色可配置通知渠道")
    name = common.str_field(body.get("name"), "name", required=True)
    kind = common.str_field(body.get("kind"), "kind", default="wecom").lower()
    if kind not in ("wecom", "dingtalk", "generic"):
        raise common.ApiError(400, "validation", "kind 只能是 wecom/dingtalk/generic")
    webhook_env = common.str_field(body.get("webhook_env"), "webhook_env", default="ALERT_WEBHOOK_URL")
    if not re.match(r"^[A-Z][A-Z0-9_]*$", webhook_env):
        raise common.ApiError(400, "validation", "webhook_env 必须是大写环境变量名")
    channel_id = conn.execute(
        "INSERT INTO notify_channels(name, kind, webhook_env, status, created_by, created_at) VALUES (?,?,?,?,?,?)",
        (name, kind, webhook_env, "enabled", user["id"], db.iso()),
    ).lastrowid
    common.audit(conn, user["id"], "登记通知渠道", "notify_channel", channel_id, f"{name}（{kind}）")
    conn.commit()
    row = conn.execute("SELECT * FROM notify_channels WHERE id=?", (channel_id,)).fetchone()
    return 201, _channel_json(row)


def _payload(kind: str, text: str) -> dict:
    if kind in ("wecom", "dingtalk"):
        return {"msgtype": "text", "text": {"content": text}}
    return {"text": text}


def _send(url: str, kind: str, text: str) -> None:
    request = urllib.request.Request(
        url, data=json.dumps(_payload(kind, text), ensure_ascii=False).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:160]
        raise RuntimeError(f"webhook HTTP {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"webhook 连接失败：{exc}") from exc


def _send_channel(ctx, channel, text: str) -> dict:
    conn, user = ctx["conn"], ctx["user"]
    url = _env(channel["webhook_env"] or "")
    if not url:
        raise common.ApiError(400, "notify_not_configured",
                              f"渠道 {channel['name']} 未配置 {channel['webhook_env']}")
    try:
        _send(url, channel["kind"], text)
    except RuntimeError as exc:
        detail = str(exc)[:300]
        conn.execute(
            "INSERT INTO integration_calls(integration, action, target, status, external_id, detail, created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            ("notify", "send", f"channel:#{channel['id']}", "failed", "", detail, db.iso()))
        common.audit(conn, user["id"], "发送通知失败", "notify_channel", channel["id"], detail)
        conn.commit()
        raise common.ApiError(502, "notify_upstream", f"通知发送失败：{detail}")
    conn.execute(
        "INSERT INTO integration_calls(integration, action, target, status, external_id, detail, created_at) "
        "VALUES (?,?,?,?,?,?,?)",
        ("notify", "send", f"channel:#{channel['id']}", "succeeded", "", f"{channel['kind']} 发送成功", db.iso()))
    common.audit(conn, user["id"], "发送通知", "notify_channel", channel["id"], text[:80])
    conn.commit()
    return {"channel": channel["name"], "kind": channel["kind"], "status": "sent"}


def test_channel(ctx):
    common.require(ctx["user"], "model:read", "仅管理/平台审批角色可测试通知")
    channel = ctx["conn"].execute(
        "SELECT * FROM notify_channels WHERE id=?", (int(ctx["params"]["id"]),)).fetchone()
    if not channel:
        raise common.ApiError(404, "not_found", "通知渠道不存在")
    result = _send_channel(ctx, channel, "【MediAgent】通知渠道测试：配置成功。此消息由测试操作触发。")
    return 200, {"ok": True, **result}


def notify_alerts(ctx):
    common.require(ctx["user"], "model:read", "仅管理/平台审批角色可发送告警")
    conn = ctx["conn"]
    channels = conn.execute("SELECT * FROM notify_channels WHERE status='enabled'").fetchall()
    configured = [channel for channel in channels if _env(channel["webhook_env"] or "")]
    if not configured:
        raise common.ApiError(400, "notify_not_configured",
                              "无已配置通知渠道：请设置 ALERT_WEBHOOK_URL 或登记渠道对应的环境变量")
    _, alerts = ops.alerts({"conn": conn, "user": ctx["user"], "query": {}})
    items = alerts.get("items") or []
    lines = ["【MediAgent 运营告警】"] + [
        f"- [{item['severity']}] {item['title']}：{item['detail']}" for item in items
    ] if items else ["【MediAgent 运营告警】当前无告警。"]
    text = "\n".join(lines)
    sent = []
    for channel in configured:
        sent.append(_send_channel(ctx, channel, text))
    return 200, {"ok": True, "alerts": len(items), "sent": sent}


ROUTES = [
    ("GET", re.compile(r"^/api/ops/notify/channels$"), list_channels),
    ("POST", re.compile(r"^/api/ops/notify/channels$"), create_channel),
    ("POST", re.compile(r"^/api/ops/notify/channels/(?P<id>\d+)/test$"), test_channel),
    ("POST", re.compile(r"^/api/ops/alerts/notify$"), notify_alerts),
]
