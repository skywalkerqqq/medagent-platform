"""报告初稿编辑器：生成草稿 → 医生编辑 → 签名，记录修改率与审计。"""
from __future__ import annotations

import difflib
import json
import re

import common
import db
import engine


def _json(row) -> dict:
    data = dict(row)
    data["missing_fields"] = common.loads(data.get("missing_fields"), []) or []
    return data


def _load(conn, report_id: int):
    row = conn.execute("SELECT * FROM report_drafts WHERE id=?", (int(report_id),)).fetchone()
    if not row:
        raise common.ApiError(404, "not_found", "报告草稿不存在")
    return row


def _parse_report(text: str) -> dict:
    raw = str(text or "").strip()
    raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        raw = match.group(0)
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except ValueError:
        pass
    return {"findings": str(text or ""), "impression": "", "recommendation": "", "missing_fields": []}


def _edit_rate(original: str, current: str) -> float:
    if not original and not current:
        return 0.0
    ratio = difflib.SequenceMatcher(None, original or "", current or "").ratio()
    return round(max(0.0, 1.0 - ratio), 4)


def list_reports(ctx):
    common.require(ctx["user"], "report:read")
    query = ctx["query"]
    where, params = [], []
    if query.get("app_id"):
        where.append("app_id=?")
        params.append(common.int_field(query["app_id"], "app_id", minimum=1))
    if query.get("status"):
        where.append("status=?")
        params.append(query["status"])
    if query.get("q"):
        where.append("(findings LIKE ? OR impression LIKE ? OR exam_type LIKE ?)")
        keyword = f"%{query['q']}%"
        params.extend([keyword, keyword, keyword])
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    limit, offset = common.pagination(query)
    total = ctx["conn"].execute(f"SELECT COUNT(*) AS c FROM report_drafts{clause}", params).fetchone()["c"]
    rows = ctx["conn"].execute(
        f"SELECT * FROM report_drafts{clause} ORDER BY id DESC LIMIT ? OFFSET ?",
        params + [limit, offset]).fetchall()
    return 200, {"items": [_json(row) for row in rows], "total": total}


def create_draft(ctx):
    conn, user, body = ctx["conn"], ctx["user"], ctx["body"]
    common.require(user, "report:write", "无报告编辑权限")
    app_id = common.int_field(body.get("app_id"), "app_id", minimum=1)
    app = conn.execute("SELECT * FROM apps WHERE id=?", (app_id,)).fetchone()
    if not app:
        raise common.ApiError(404, "not_found", "应用不存在")
    if app["template_key"] != "med-report":
        raise common.ApiError(400, "validation", "仅报告初稿模板（med-report）可生成报告草稿")
    if app["status"] == "disabled":
        raise common.ApiError(409, "conflict", "应用已停用")
    findings = common.str_field(body.get("findings") or body.get("query"), "findings", required=True)
    exam_type = common.str_field(body.get("exam_type"), "exam_type", default="未指定检查")
    patient_ref = common.str_field(body.get("patient_ref"), "patient_ref", default="")
    result = engine.generate(conn, app, findings, user["department"] or "", user_id=user["id"])
    parsed = _parse_report(result["output"])
    code = "RPT-" + str(conn.execute("SELECT COUNT(*) AS c FROM report_drafts").fetchone()["c"] + 1).zfill(4)
    report_id = conn.execute(
        """INSERT INTO report_drafts(code, app_id, patient_ref, exam_type, findings_original, findings,
               impression_original, impression, recommendation_original, recommendation,
               missing_fields, status, created_by, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (code, app_id, patient_ref, exam_type, findings,
         parsed.get("findings") or findings,
         parsed.get("impression") or "", parsed.get("impression") or "",
         parsed.get("recommendation") or "", parsed.get("recommendation") or "",
         common.dumps(parsed.get("missing_fields") or []),
         "draft", user["id"], db.iso(), db.iso()),
    ).lastrowid
    common.audit(conn, user["id"], "生成报告草稿", "report", report_id, f"{code} {exam_type}")
    conn.commit()
    return 201, _json(_load(conn, report_id))


def get_report(ctx):
    common.require(ctx["user"], "report:read")
    return 200, _json(_load(ctx["conn"], ctx["params"]["id"]))


def update_report(ctx):
    conn, user, body = ctx["conn"], ctx["user"], ctx["body"]
    common.require(user, "report:write", "无报告编辑权限")
    report_id = int(ctx["params"]["id"])
    row = _load(conn, report_id)
    if row["status"] != "draft":
        raise common.ApiError(409, "conflict", "已签名报告不可修改")
    findings = body.get("findings", row["findings"]) or ""
    impression = body.get("impression", row["impression"]) or ""
    recommendation = body.get("recommendation", row["recommendation"]) or ""
    missing = common.loads(row["missing_fields"], []) or []
    conn.execute(
        "UPDATE report_drafts SET findings=?, impression=?, recommendation=?, missing_fields=?, updated_at=? WHERE id=?",
        (str(findings).strip(), str(impression).strip(), str(recommendation).strip(),
         common.dumps(missing), db.iso(), report_id),
    )
    common.audit(conn, user["id"], "编辑报告草稿", "report", report_id, "保存修改")
    conn.commit()
    return 200, _json(_load(conn, report_id))


def sign_report(ctx):
    conn, user = ctx["conn"], ctx["user"]
    common.require(user, "report:write", "无报告签名权限")
    report_id = int(ctx["params"]["id"])
    row = _load(conn, report_id)
    if row["status"] != "draft":
        return 200, _json(row)
    original = f"{row['findings_original'] or ''}\n{row['impression_original'] or ''}\n{row['recommendation_original'] or ''}"
    current = f"{row['findings'] or ''}\n{row['impression'] or ''}\n{row['recommendation'] or ''}"
    rate = _edit_rate(original, current)
    conn.execute(
        "UPDATE report_drafts SET status='signed', editor_id=?, edit_rate=?, signed_at=?, updated_at=? WHERE id=?",
        (user["id"], rate, db.iso(), db.iso(), report_id),
    )
    common.audit(conn, user["id"], "签名报告", "report", report_id,
                 f"修改率 {round(rate * 100, 1)}%（编辑人={user['id']}）")
    conn.commit()
    return 200, _json(_load(conn, report_id))


ROUTES = [
    ("GET", re.compile(r"^/api/reports$"), list_reports),
    ("POST", re.compile(r"^/api/reports/draft$"), create_draft),
    ("GET", re.compile(r"^/api/reports/(?P<id>\d+)$"), get_report),
    ("PUT", re.compile(r"^/api/reports/(?P<id>\d+)$"), update_report),
    ("POST", re.compile(r"^/api/reports/(?P<id>\d+)/sign$"), sign_report),
]
