"""通用工具：错误、权限、审计、入参。"""
from __future__ import annotations

import json

ROLE_PERMISSIONS = {
    "admin": {"admin", "app:create", "app:edit", "app:submit", "app:trial", "approval:dept",
              "approval:platform", "eval:run", "knowledge:write", "knowledge:review",
              "audit:read", "audit:export", "model:read", "model:write", "badcase:manage",
              "metrics:read", "patient:manage", "memory:read", "memory:write",
              "report:read", "report:write"},
    "creator": {"app:create", "app:edit", "app:submit", "app:trial", "knowledge:read",
                "metrics:read", "memory:read", "memory:write", "report:read", "report:write"},
    "dept_approver": {"approval:dept", "app:trial", "knowledge:read", "audit:read",
                      "metrics:read", "memory:read", "report:read"},
    "platform_approver": {"approval:platform", "audit:read", "audit:export", "model:read",
                          "badcase:manage", "metrics:read", "app:trial", "knowledge:read",
                          "memory:read", "report:read"},
    "doctor": {"app:trial", "knowledge:read", "metrics:read", "memory:read", "memory:write",
               "report:read", "report:write"},
    "knowledge_ops": {"knowledge:write", "knowledge:review", "knowledge:read",
                      "metrics:read", "memory:read", "memory:write", "report:read"},
    "evaluator": {"eval:run", "knowledge:read", "metrics:read", "app:trial", "memory:read",
                  "report:read"},
    "patient": {"patient:use"},
}


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, details=None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details


def has(user, permission: str) -> bool:
    return permission in ROLE_PERMISSIONS.get(user["role"], set())


def require(user, permission: str, message: str = "无权限执行该操作"):
    if not has(user, permission):
        raise ApiError(403, "forbidden", message)


def audit(conn, actor, action, target_type="", target_id="", detail=""):
    conn.execute(
        "INSERT INTO audit_logs(actor, action, target_type, target_id, detail, created_at) "
        "VALUES (?,?,?,?,?,?)",
        (actor, action, target_type, str(target_id), detail, db_iso()),
    )


def db_iso() -> str:
    from datetime import datetime
    return datetime.now().astimezone().isoformat(timespec="seconds")


def str_field(value, name, required=False, default=""):
    if value is None:
        if required:
            raise ApiError(400, "validation", f"{name} 不能为空")
        return default
    text = str(value).strip()
    if required and not text:
        raise ApiError(400, "validation", f"{name} 不能为空")
    return text


def int_field(value, name, default=0, minimum=None, maximum=None):
    if value is None:
        return default
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ApiError(400, "validation", f"{name} 必须是整数")
    if minimum is not None and number < minimum:
        raise ApiError(400, "validation", f"{name} 不能小于 {minimum}")
    if maximum is not None and number > maximum:
        raise ApiError(400, "validation", f"{name} 不能大于 {maximum}")
    return number


def pagination(query):
    try:
        limit = max(1, min(int(query.get("limit", 50)), 200))
        offset = max(0, int(query.get("offset", 0)))
    except (TypeError, ValueError):
        raise ApiError(400, "validation", "分页参数非法")
    return limit, offset


def loads(value, default=None):
    if value is None or value == "":
        return default
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except (ValueError, TypeError):
        return default


def dumps(value) -> str:
    return json.dumps(value, ensure_ascii=False)
