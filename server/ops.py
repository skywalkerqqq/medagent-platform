"""运营指标、BadCase 与审计。"""
from __future__ import annotations

import re

import common
import db

METRIC_DEFS = [
    {"key": "apps_total", "name": "应用总数", "definition": "全部状态应用数", "source": "apps"},
    {"key": "apps_published", "name": "已发布应用", "definition": "status=published", "source": "apps"},
    {"key": "eval_pass_rate", "name": "评测通过率", "definition": "通过门禁的评测运行 / 评测运行总数", "source": "eval_runs"},
    {"key": "badcase_open", "name": "未闭环 BadCase", "definition": "status != closed", "source": "badcases"},
    {"key": "safety_high", "name": "高风险安全事件", "definition": "severity=high", "source": "safety_events"},
    {"key": "model_calls", "name": "模型调用次数", "definition": "model_calls 总数", "source": "model_calls"},
    {"key": "degrade_rate", "name": "模型降级率", "definition": "degraded=1 / 调用总数", "source": "model_calls"},
    {"key": "p95_latency_ms", "name": "模型 P95 延迟", "definition": "调用延迟第 95 百分位（ms）", "source": "model_calls"},
    {"key": "knowledge_approved", "name": "生效知识数", "definition": "status=approved 且未过期", "source": "knowledge_docs"},
    {"key": "knowledge_pending", "name": "待审核知识", "definition": "status=pending", "source": "knowledge_docs"},
]


def _scalar(conn, sql, params=()):
    return conn.execute(sql, params).fetchone()[0]


def metrics_snapshot(conn) -> dict:
    total_apps = _scalar(conn, "SELECT COUNT(*) FROM apps")
    published = _scalar(conn, "SELECT COUNT(*) FROM apps WHERE status='published'")
    eval_total = _scalar(conn, "SELECT COUNT(*) FROM eval_runs")
    eval_passed = _scalar(conn, "SELECT COUNT(*) FROM eval_runs WHERE passed=1")
    calls = conn.execute("SELECT latency_ms, degraded FROM model_calls").fetchall()
    latencies = sorted(row["latency_ms"] for row in calls if row["latency_ms"])
    p95 = latencies[min(len(latencies) - 1, int(len(latencies) * 0.95))] if latencies else 0
    values = {
        "apps_total": total_apps,
        "apps_published": published,
        "eval_pass_rate": round(eval_passed / eval_total, 3) if eval_total else None,
        "badcase_open": _scalar(conn, "SELECT COUNT(*) FROM badcases WHERE status != 'closed'"),
        "safety_high": _scalar(conn, "SELECT COUNT(*) FROM safety_events WHERE severity='high'"),
        "model_calls": len(calls),
        "degrade_rate": round(sum(1 for row in calls if row["degraded"]) / len(calls), 3) if calls else 0,
        "p95_latency_ms": p95,
        "knowledge_approved": _scalar(
            conn,
            "SELECT COUNT(*) FROM knowledge_docs WHERE status='approved' "
            "AND (expires_at IS NULL OR expires_at='' OR expires_at > ?)", (db.iso(),)),
        "knowledge_pending": _scalar(conn, "SELECT COUNT(*) FROM knowledge_docs WHERE status='pending'"),
    }
    return {"values": values, "definitions": METRIC_DEFS}


def metrics(ctx):
    common.require(ctx["user"], "metrics:read")
    return 200, metrics_snapshot(ctx["conn"])


def dashboard(ctx):
    conn, user = ctx["conn"], ctx["user"]
    common.require(user, "metrics:read")
    metrics_data = metrics_snapshot(conn)["values"]
    by_status = {row["status"]: row["c"] for row in conn.execute(
        "SELECT status, COUNT(*) AS c FROM apps GROUP BY status").fetchall()}
    pending_approvals = conn.execute(
        "SELECT COUNT(*) FROM approvals WHERE status='pending'").fetchone()[0]
    checklist = [
        {"item": "合并 W1–W13 主计划（POC 复用边界）", "done": False},
        {"item": "首批医院/科室/临床/RA 资源确认", "done": False},
        {"item": "患者专属功能未通过前保持关闭", "done": True},
        {"item": "X-User-Id 仅限隔离 mock（本平台已改为服务端 Token）", "done": True},
        {"item": "模板评测集/阈值/高风险阻断项冻结", "done": True},
        {"item": "医疗 AI 风险分级与人工接管流程", "done": True},
        {"item": "接口错误/超时/重试/幂等/审计约束", "done": True},
        {"item": "备份/性能/可用性验收方式", "done": False},
        {"item": "预算/资源/依赖责任人确认", "done": False},
        {"item": "G1/POC/G2/生产准入区别已明确", "done": True},
    ]
    return 200, {
        "metrics": metrics_data,
        "apps_by_status": by_status,
        "pending_approvals": pending_approvals,
        "recent_audit": [dict(row) for row in conn.execute(
            "SELECT * FROM audit_logs ORDER BY id DESC LIMIT 6").fetchall()],
        "release_checklist": checklist,
        "recent_apps": [dict(row) for row in conn.execute(
            "SELECT id, code, name, status, current_version, department FROM apps ORDER BY id DESC LIMIT 5"
        ).fetchall()],
    }


def alerts(ctx):
    common.require(ctx["user"], "metrics:read")
    snapshot = metrics_snapshot(ctx["conn"])["values"]
    items = []
    if snapshot["safety_high"]:
        items.append({"severity": "high", "title": "存在高风险安全事件",
                      "detail": f"{snapshot['safety_high']} 条高风险事件待处置（阻断发布）",
                      "action": "前往安全事件/发布检查处置"})
    if snapshot["badcase_open"] > 2:
        items.append({"severity": "medium", "title": "BadCase 积压",
                      "detail": f"{snapshot['badcase_open']} 条未闭环", "action": "运营台分派/关闭"})
    if snapshot["eval_pass_rate"] is not None and snapshot["eval_pass_rate"] < 0.7:
        items.append({"severity": "medium", "title": "评测通过率偏低",
                      "detail": f"当前 {round(snapshot['eval_pass_rate'] * 100)}%，低于 70%",
                      "action": "检查模板/知识/评测集"})
    if snapshot["degrade_rate"] and snapshot["degrade_rate"] > 0.2:
        items.append({"severity": "low", "title": "模型降级率偏高",
                      "detail": f"降级率 {round(snapshot['degrade_rate'] * 100)}%",
                      "action": "检查主模型可用性/策略链"})
    failures = ctx["conn"].execute(
        "SELECT COUNT(*) FROM model_calls WHERE error_code != ''").fetchone()[0]
    if failures:
        items.append({"severity": "medium", "title": "模型调用失败",
                      "detail": f"{failures} 次失败（含真实上游失败）", "action": "查看模型调用记录"})
    if snapshot["knowledge_pending"] > 5:
        items.append({"severity": "low", "title": "知识待审核积压",
                      "detail": f"{snapshot['knowledge_pending']} 条待审核", "action": "知识运营处理"})
    return 200, {"items": items, "generated_at": db.iso()}


def list_badcases(ctx):
    common.require(ctx["user"], "metrics:read")
    query = ctx["query"]
    where, params = [], []
    if query.get("status"):
        where.append("b.status=?")
        params.append(query["status"])
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    rows = ctx["conn"].execute(
        f"""SELECT b.*, a.name AS app_name FROM badcases b LEFT JOIN apps a ON a.id=b.app_id
            {clause} ORDER BY b.id DESC""", params).fetchall()
    return 200, {"items": [dict(row) for row in rows]}


def create_badcase(ctx):
    conn, user = ctx["conn"], ctx["user"]
    common.require(user, "badcase:manage")
    body = ctx["body"]
    app_id = common.int_field(body.get("app_id"), "app_id", minimum=1)
    question = common.str_field(body.get("question"), "question", required=True)
    output = common.str_field(body.get("output"), "output", required=True)
    category = common.str_field(body.get("category"), "category", default="quality")
    severity = common.str_field(body.get("severity"), "severity", default="medium")
    badcase_id = conn.execute(
        "INSERT INTO badcases(app_id, source, question, output, category, severity, status, created_at) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (app_id, user["id"], question, output, category, severity, "open", db.iso()),
    ).lastrowid
    common.audit(conn, user["id"], "登记 BadCase", "badcase", badcase_id, category)
    conn.commit()
    return 201, {"id": badcase_id, "status": "open"}


def update_badcase(ctx):
    conn, user = ctx["conn"], ctx["user"]
    common.require(user, "badcase:manage")
    badcase_id = int(ctx["params"]["id"])
    row = conn.execute("SELECT * FROM badcases WHERE id=?", (badcase_id,)).fetchone()
    if not row:
        raise common.ApiError(404, "not_found", "BadCase 不存在")
    body = ctx["body"]
    action = common.str_field(body.get("action"), "action", required=True)
    if action == "assign":
        assignee = common.str_field(body.get("assignee"), "assignee", required=True)
        conn.execute("UPDATE badcases SET assignee=?, status='assigned' WHERE id=?", (assignee, badcase_id))
        common.audit(conn, user["id"], "分派 BadCase", "badcase", badcase_id, assignee)
    elif action == "close":
        resolution = common.str_field(body.get("resolution"), "resolution", required=True)
        conn.execute(
            "UPDATE badcases SET status='closed', resolution=?, closed_at=? WHERE id=?",
            (resolution, db.iso(), badcase_id))
        common.audit(conn, user["id"], "关闭 BadCase", "badcase", badcase_id, resolution)
    else:
        raise common.ApiError(400, "validation", "action 只能是 assign/close")
    conn.commit()
    return 200, dict(conn.execute("SELECT * FROM badcases WHERE id=?", (badcase_id,)).fetchone())


def list_audit(ctx):
    common.require(ctx["user"], "audit:read")
    limit, offset = common.pagination(ctx["query"])
    rows = ctx["conn"].execute(
        "SELECT * FROM audit_logs ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset)).fetchall()
    return 200, {"items": [dict(row) for row in rows]}


def export_audit(ctx):
    common.require(ctx["user"], "audit:export", "仅管理员/平台审批人可导出审计")
    rows = ctx["conn"].execute("SELECT * FROM audit_logs ORDER BY id").fetchall()
    common.audit(ctx["conn"], ctx["user"]["id"], "导出审计", "audit", "", f"{len(rows)} 条")
    ctx["conn"].commit()
    return 200, {"exported": len(rows), "items": [dict(row) for row in rows],
                 "note": "导出动作已留痕；生产环境需审批与水印"}


def list_handoffs(ctx):
    common.require(ctx["user"], "patient:manage")
    rows = ctx["conn"].execute("SELECT * FROM handoffs ORDER BY id DESC").fetchall()
    return 200, {"items": [dict(row) for row in rows]}


ROUTES = [
    ("GET", re.compile(r"^/api/ops/metrics$"), metrics),
    ("GET", re.compile(r"^/api/ops/alerts$"), alerts),
    ("GET", re.compile(r"^/api/dashboard$"), dashboard),
    ("GET", re.compile(r"^/api/badcases$"), list_badcases),
    ("POST", re.compile(r"^/api/badcases$"), create_badcase),
    ("POST", re.compile(r"^/api/badcases/(?P<id>\d+)$"), update_badcase),
    ("GET", re.compile(r"^/api/audit$"), list_audit),
    ("GET", re.compile(r"^/api/audit/export$"), export_audit),
    ("GET", re.compile(r"^/api/handoffs$"), list_handoffs),
]
