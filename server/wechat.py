"""微信小程序登录适配（v1.1 患者端联动）。

- 配置 WX_APPID/WX_SECRET 时调用 jscode2session；未配置时走 dev mock（POC 演示用）。
- 微信 openid 仅用于建立平台会话，不视为医疗身份；患者专属数据仍须绑定 + 授权（FR-012）。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

import auth
import common
import db

DEFAULT_URL = "https://api.weixin.qq.com/sns/jscode2session"


def config() -> dict | None:
    appid = (os.environ.get("WX_APPID") or "").strip()
    secret = (os.environ.get("WX_SECRET") or "").strip()
    if not (appid and secret):
        return None
    return {"appid": appid, "secret": secret,
            "url": (os.environ.get("WX_CODE2SESSION_URL") or DEFAULT_URL).strip()}


def _mock_openid(code: str) -> str:
    return "dev-" + hashlib.md5(code.encode("utf-8")).hexdigest()[:12]


def code2session(code: str) -> dict:
    cfg = config()
    if not cfg:
        return {"openid": _mock_openid(code), "mode": "mock"}
    query = urllib.parse.urlencode({
        "appid": cfg["appid"], "secret": cfg["secret"],
        "js_code": code, "grant_type": "authorization_code",
    })
    url = cfg["url"] + ("&" if "?" in cfg["url"] else "?") + query
    try:
        with urllib.request.urlopen(url, timeout=8) as resp:
            body = json.loads(resp.read().decode("utf-8", "replace") or "{}")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, OSError) as exc:
        raise common.ApiError(502, "wx_upstream", f"微信登录服务不可用：{exc}") from exc
    if body.get("errcode"):
        raise common.ApiError(401, "wx_login_failed",
                              f"微信登录失败：{body.get('errcode')} {body.get('errmsg') or ''}".strip())
    openid = str(body.get("openid") or "").strip()
    if not openid:
        raise common.ApiError(401, "wx_login_failed", "微信登录失败：未返回 openid")
    return {"openid": openid, "mode": "wechat"}


def wx_login(ctx):
    conn, body = ctx["conn"], ctx["body"]
    code = common.str_field(body.get("code"), "code", required=True)
    info = code2session(code)
    openid = info["openid"]
    uid = "wx_" + hashlib.sha1(openid.encode("utf-8")).hexdigest()[:10]
    user = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    created = False
    if user is None:
        conn.execute(
            "INSERT INTO users(id, name, role, department, password_hash, color) VALUES (?,?,?,?,?,?)",
            (uid, "微信访客 " + openid[-4:].upper(), "patient", "患者", "", "#0EA5E9"),
        )
        user = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
        created = True
    issued = auth.issue_token(conn, uid)
    common.audit(conn, uid, "微信登录", "user", uid, f"{info['mode']} {openid[:6]}***")
    conn.commit()
    return 200, {
        "token": issued["token"], "expires_at": issued["expires_at"],
        "user": auth.user_json(user), "mode": info["mode"], "is_new_user": created,
        "note": "微信身份仅用于会话；患者数据需完成绑定与授权后才能访问",
    }


ROUTES = [
    ("POST", re.compile(r"^/api/auth/wx-login$"), wx_login),
]
