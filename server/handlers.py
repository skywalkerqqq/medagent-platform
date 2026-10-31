"""路由聚合与基础端点。"""
from __future__ import annotations

import re

import apps
import auth
import common
import db
import eval_center
import knowledge
import models
import ops
import patient
import safety
import templates
import wechat

VERSION = "1.1.0"


def health(ctx):
    return 200, {"status": "ok", "version": VERSION, "platform": "MediAgent 医疗 AI 中台 v1.1",
                 "auth": "Bearer token（服务端会话，非 X-User-Id）", "time": db.iso()}


def users(ctx):
    common.require(ctx["user"], "admin", "仅管理员可查看用户列表")
    rows = ctx["conn"].execute("SELECT id, name, role, department, color FROM users ORDER BY id").fetchall()
    return 200, {"items": [dict(row) for row in rows]}


ROUTES = [
    ("GET", re.compile(r"^/api/health$"), health),
    ("GET", re.compile(r"^/api/users$"), users),
] + auth.ROUTES + templates.ROUTES + knowledge.ROUTES + models.ROUTES + eval_center.ROUTES + \
    apps.ROUTES + ops.ROUTES + patient.ROUTES + safety.ROUTES + wechat.ROUTES


def dispatch(method: str, path: str, ctx: dict):
    normalized = path.rstrip("/") or "/"
    matched = False
    for route_method, pattern, handler in ROUTES:
        match = pattern.match(normalized)
        if not match:
            continue
        matched = True
        if route_method == method:
            ctx["params"] = match.groupdict()
            return handler(ctx)
    if matched:
        raise common.ApiError(405, "method_not_allowed", f"接口不支持 {method}")
    raise common.ApiError(404, "not_found", f"接口不存在：{normalized}")
