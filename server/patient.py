"""患者端（小程序）API：绑定、授权、报告、随访与异常转人工。"""
from __future__ import annotations

import re

import common
import db
import safety

VERIFY_CODE = "654321"
RISK_WORDS = ("胸痛", "呼吸困难", "出血", "昏迷", "抽搐", "剧烈头痛")
DISCLAIMER = safety.DISCLAIMER


def _require_patient(user):
    if user["role"] == "admin":
        return
    common.require(user, "patient:use", "仅患者身份可访问患者端")


def _binding(conn, user_id):
    return conn.execute(
        "SELECT * FROM patient_bindings WHERE user_id=? AND status='active' ORDER BY id DESC LIMIT 1",
        (user_id,),
    ).fetchone()


def bind(ctx):
    conn, user, body = ctx["conn"], ctx["user"], ctx["body"]
    _require_patient(user)
    patient_ref = common.str_field(body.get("patient_ref"), "patient_ref", required=True)
    code = common.str_field(body.get("verify_code"), "verify_code", required=True)
    if code != VERIFY_CODE:
        raise common.ApiError(400, "verify_failed", "身份核验失败（POC 演示验证码 654321）")
    patient = conn.execute("SELECT * FROM patients WHERE patient_ref=?", (patient_ref,)).fetchone()
    if not patient:
        raise common.ApiError(404, "not_found", "患者不存在或未授权")
    conn.execute(
        "UPDATE patient_bindings SET status='revoked', revoked_at=? WHERE user_id=? AND status='active'",
        (db.iso(), user["id"]),
    )
    consent = common.loads(body.get("consent"), None) or ["report", "followup"]
    conn.execute(
        "INSERT INTO patient_bindings(user_id, patient_ref, consent, status, bound_at) VALUES (?,?,?,?,?)",
        (user["id"], patient_ref, common.dumps(consent), "active", db.iso()),
    )
    common.audit(conn, user["id"], "患者绑定", "patient", patient_ref, f"授权 {consent}")
    conn.commit()
    return 200, {"bound": True, "patient_ref": patient_ref, "consent": consent,
                 "name_mask": patient["name_mask"], "note": "仅访问授权范围内服务"}


def me(ctx):
    conn, user = ctx["conn"], ctx["user"]
    _require_patient(user)
    binding = _binding(conn, user["id"])
    if not binding:
        return 200, {"bound": False, "consent": [], "reports": 0, "tasks": 0}
    patient = conn.execute("SELECT * FROM patients WHERE patient_ref=?", (binding["patient_ref"],)).fetchone()
    consent = common.loads(binding["consent"], []) or []
    reports = 0
    tasks = 0
    if "report" in consent:
        reports = conn.execute(
            "SELECT COUNT(*) FROM reports WHERE patient_ref=? AND approved_for_patient=1",
            (binding["patient_ref"],)).fetchone()[0]
    if "followup" in consent:
        tasks = conn.execute(
            "SELECT COUNT(*) FROM followup_tasks WHERE patient_ref=? AND status IN ('pending','submitted')",
            (binding["patient_ref"],)).fetchone()[0]
    return 200, {
        "bound": True,
        "patient_ref": binding["patient_ref"],
        "name_mask": patient["name_mask"] if patient else "",
        "consent": consent,
        "reports": reports,
        "tasks": tasks,
        "bound_at": binding["bound_at"],
    }


def revoke(ctx):
    conn, user, body = ctx["conn"], ctx["user"], ctx["body"]
    _require_patient(user)
    binding = _binding(conn, user["id"])
    if not binding:
        raise common.ApiError(409, "not_bound", "当前无有效绑定")
    action = common.str_field(body.get("action"), "action", default="revoke")
    if action == "unbind":
        conn.execute("UPDATE patient_bindings SET status='revoked', revoked_at=? WHERE id=?",
                     (db.iso(), binding["id"]))
        detail = "解绑"
    else:
        conn.execute("UPDATE patient_bindings SET consent=? WHERE id=?", (common.dumps([]), binding["id"]))
        detail = "撤回授权"
    common.audit(conn, user["id"], f"患者{detail}", "patient", binding["patient_ref"], detail)
    conn.commit()
    return 200, {"ok": True, "action": action}


def reports(ctx):
    conn, user = ctx["conn"], ctx["user"]
    _require_patient(user)
    binding = _binding(conn, user["id"])
    if not binding:
        raise common.ApiError(403, "not_bound", "未绑定，不能访问患者数据")
    consent = common.loads(binding["consent"], []) or []
    if "report" not in consent:
        raise common.ApiError(403, "no_consent", "未授权报告查询")
    rows = conn.execute(
        "SELECT * FROM reports WHERE patient_ref=? AND approved_for_patient=1 ORDER BY id DESC",
        (binding["patient_ref"],)).fetchall()
    return 200, {"items": [dict(row) for row in rows]}


def followups(ctx):
    conn, user = ctx["conn"], ctx["user"]
    _require_patient(user)
    binding = _binding(conn, user["id"])
    if not binding:
        raise common.ApiError(403, "not_bound", "未绑定，不能访问患者数据")
    consent = common.loads(binding["consent"], []) or []
    if "followup" not in consent:
        raise common.ApiError(403, "no_consent", "未授权随访服务")
    rows = conn.execute(
        """SELECT id, node, due_at, status, form, risk_flag, created_at, submitted_at
           FROM followup_tasks WHERE patient_ref=? ORDER BY id DESC""",
        (binding["patient_ref"],)).fetchall()
    items = []
    for row in rows:
        item = dict(row)
        item["form"] = common.loads(item["form"], []) or []
        items.append(item)
    return 200, {"items": items}


def submit_followup(ctx):
    conn, user, body = ctx["conn"], ctx["user"], ctx["body"]
    _require_patient(user)
    binding = _binding(conn, user["id"])
    if not binding:
        raise common.ApiError(403, "not_bound", "未绑定，不能访问患者数据")
    consent = common.loads(binding["consent"], []) or []
    if "followup" not in consent:
        raise common.ApiError(403, "no_consent", "未授权随访服务")
    task_id = int(ctx["params"]["id"])
    task = conn.execute("SELECT * FROM followup_tasks WHERE id=?", (task_id,)).fetchone()
    if not task or task["patient_ref"] != binding["patient_ref"]:
        raise common.ApiError(404, "not_found", "随访任务不存在或无权限")
    answers = body.get("answers") or {}
    if not isinstance(answers, dict):
        raise common.ApiError(400, "validation", "answers 必须是对象")
    text = " ".join(str(value) for value in answers.values())
    risk = any(word in text for word in RISK_WORDS)
    now = db.iso()
    if risk:
        conn.execute(
            "UPDATE followup_tasks SET answers=?, risk_flag=1, status='handoff', submitted_at=? WHERE id=?",
            (common.dumps(answers), now, task_id))
        handoff_id = conn.execute(
            "INSERT INTO handoffs(patient_ref, task_id, reason, status, created_at) VALUES (?,?,?,?,?)",
            (binding["patient_ref"], task_id, "随访问卷命中危险信号", "pending", now),
        ).lastrowid
        common.audit(conn, user["id"], "随访异常转人工", "followup", task_id, f"handoff #{handoff_id}")
        conn.commit()
        return 200, {
            "risk_flag": True,
            "handoff": True,
            "handoff_id": handoff_id,
            "message": "已识别需关注情况，已生成人工处置待办。若症状加重，请立即就医或拨打急救电话。",
            "disclaimer": DISCLAIMER,
            "note": "转人工未接单时系统将提示线下就医渠道，并按运营告警处理",
        }
    conn.execute(
        "UPDATE followup_tasks SET answers=?, risk_flag=0, status='submitted', submitted_at=? WHERE id=?",
        (common.dumps(answers), now, task_id))
    common.audit(conn, user["id"], "提交随访", "followup", task_id, "无危险信号")
    conn.commit()
    return 200, {"risk_flag": False, "handoff": False, "message": "已记录，感谢反馈。",
                 "disclaimer": DISCLAIMER}


ROUTES = [
    ("POST", re.compile(r"^/api/patient/bind$"), bind),
    ("GET", re.compile(r"^/api/patient/me$"), me),
    ("POST", re.compile(r"^/api/patient/revoke$"), revoke),
    ("GET", re.compile(r"^/api/patient/reports$"), reports),
    ("GET", re.compile(r"^/api/patient/followups$"), followups),
    ("POST", re.compile(r"^/api/patient/followups/(?P<id>\d+)/submit$"), submit_followup),
]
