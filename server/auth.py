"""登录、会话与权限。非 mock 环境不使用 X-User-Id 作为身份。"""
from __future__ import annotations

import hashlib
import re
import secrets
from datetime import timedelta

import common
import db

TOKEN_TTL = timedelta(hours=8)
PUBLIC_PATHS = {"/api/health", "/api/auth/login", "/api/auth/wx-login"}


def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(8)
    digest = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return f"{salt}${digest}"


def verify_password(password: str, stored: str | None) -> bool:
    if not stored or "$" not in stored:
        return False
    salt, _ = stored.split("$", 1)
    return secrets.compare_digest(hash_password(password, salt), stored)


def issue_token(conn, user_id: str) -> dict:
    conn.execute("DELETE FROM auth_sessions WHERE expires_at <= ?", (db.iso(),))
    token = secrets.token_hex(24)
    expires = db.iso(db.now() + TOKEN_TTL)
    conn.execute(
        "INSERT INTO auth_sessions(token, user_id, created_at, expires_at) VALUES (?,?,?,?)",
        (token, user_id, db.iso(), expires),
    )
    return {"token": token, "expires_at": expires}


def token_user(conn, token: str | None):
    if not token:
        return None
    row = conn.execute(
        """SELECT u.* FROM auth_sessions s JOIN users u ON u.id = s.user_id
            WHERE s.token = ? AND s.expires_at > ?""",
        (token, db.iso()),
    ).fetchone()
    return row


def bearer(headers: dict) -> str | None:
    raw = (headers or {}).get("authorization") or ""
    match = re.match(r"^Bearer\s+(\S+)$", raw.strip(), re.IGNORECASE)
    return match.group(1) if match else None


def user_json(row) -> dict:
    data = dict(row)
    data.pop("password_hash", None)
    data["permissions"] = sorted(common.ROLE_PERMISSIONS.get(data["role"], set()))
    return data


def login(ctx):
    conn, body = ctx["conn"], ctx["body"]
    username = common.str_field(body.get("username"), "username", required=True)
    password = common.str_field(body.get("password"), "password", required=True)
    user = conn.execute("SELECT * FROM users WHERE id=? OR name=?", (username, username)).fetchone()
    if not user or not verify_password(password, user["password_hash"]):
        raise common.ApiError(401, "invalid_credentials", "用户名或密码错误")
    issued = issue_token(conn, user["id"])
    common.audit(conn, user["id"], "登录", "user", user["id"], "登录成功")
    conn.commit()
    return 200, {"token": issued["token"], "expires_at": issued["expires_at"], "user": user_json(user)}


def logout(ctx):
    conn, headers = ctx["conn"], ctx["headers"]
    token = bearer(headers)
    if token:
        conn.execute("DELETE FROM auth_sessions WHERE token=?", (token,))
        conn.commit()
    return 200, {"ok": True}


def me(ctx):
    return 200, user_json(ctx["user"])


ROUTES = [
    ("POST", re.compile(r"^/api/auth/login$"), login),
    ("POST", re.compile(r"^/api/auth/logout$"), logout),
    ("GET", re.compile(r"^/api/auth/me$"), me),
]
