"""医疗 AI 安全：允许/禁止输出、风险分级、人工接管与故障安全。"""
from __future__ import annotations

import hashlib
import re

import common
import db

FORBIDDEN_PATTERNS = [
    ("diagnosis", re.compile(r"(确诊为|诊断为|可以排除|明确诊断)")),
    ("prescription", re.compile(r"(建议服用|每日\s*\d+\s*(mg|片|粒)|调整剂量|停药)")),
    ("unsafe_advice", re.compile(r"(无需就医|不用就医|可自行处理|不必就诊)")),
]

DISCLAIMER = "本结果为 AI 辅助信息，不构成诊疗建议；须由具备资质的医生复核确认。"


def scan(text: str) -> dict:
    text = text or ""
    categories = []
    for name, pattern in FORBIDDEN_PATTERNS:
        if pattern.search(text):
            categories.append(name)
    return {
        "blocked": bool(categories),
        "categories": categories,
        "severity": "high" if categories else "none",
    }


def safe_fallback(reason: str = "") -> str:
    tip = {
        "diagnosis": "该问题涉及诊断结论，AI 不能给出结论。",
        "prescription": "该问题涉及处方/用药调整，AI 不能给出建议。",
        "unsafe_advice": "该问题涉及就医决策，AI 不能替代医生判断。",
    }.get(reason, "该问题超出 AI 辅助范围。")
    return f"{tip} 已提示转人工复核，请由具备资质的医生处理。{DISCLAIMER}"


def enforce(conn, app_id, output: str, run_id=None) -> dict:
    result = scan(output)
    if result["blocked"]:
        for category in result["categories"]:
            conn.execute(
                "INSERT INTO safety_events(app_id, run_id, category, severity, action, detail, created_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (app_id, run_id, category, "high", "blocked_and_handoff",
                 f"输出命中禁止项：{category}", db.iso()),
            )
        safe = safe_fallback(result["categories"][0])
        conn.commit()
        return {"blocked": True, "output": safe, "categories": result["categories"], "handoff": True}
    return {"blocked": False, "output": output, "categories": [], "handoff": False}


def handoff_note(reason: str) -> str:
    return f"系统已生成人工处置待办（原因：{reason}），请按院内流程处理；若无法接入人工，请引导用户联系医生或急诊。" + DISCLAIMER


def fingerprint(text: str) -> str:
    return hashlib.md5((text or "").encode("utf-8")).hexdigest()[:12]


def events(ctx):
    user = ctx["user"]
    common.require(user, "audit:read", "仅审计/管理角色可查看安全事件")
    limit, offset = common.pagination(ctx["query"])
    rows = ctx["conn"].execute(
        "SELECT * FROM safety_events ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset)
    ).fetchall()
    return 200, {"items": [dict(row) for row in rows]}


ROUTES = [
    ("GET", re.compile(r"^/api/safety/events$"), events),
]
