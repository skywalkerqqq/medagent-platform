"""应用工厂：模板实例化、试跑、发布检查、双审批、发布/停用/回滚与版本快照。"""
from __future__ import annotations

import re

import common
import db
import engine
import knowledge
import memory
import templates as templates_mod


def _config(app) -> dict:
    return common.loads(app["config"], {}) or {}


def _latest_eval(conn, app_id):
    return conn.execute(
        "SELECT * FROM eval_runs WHERE app_id=? ORDER BY id DESC LIMIT 1", (app_id,)
    ).fetchone()


def _latest_passed_eval(conn, app_id):
    return conn.execute(
        "SELECT * FROM eval_runs WHERE app_id=? AND passed=1 ORDER BY id DESC LIMIT 1", (app_id,)
    ).fetchone()


def _app_json(conn, row, detail=False) -> dict:
    app = dict(row)
    app["config"] = _config(row)
    template = templates_mod.get_template(row["template_key"])
    app["template_name"] = template["name"] if template else row["template_key"]
    latest = _latest_eval(conn, row["id"])
    app["latest_eval"] = None
    if latest:
        app["latest_eval"] = {
            "id": latest["id"], "metrics": common.loads(latest["metrics"], {}),
            "gate_status": latest["gate_status"], "threshold": latest["threshold"],
            "passed": bool(latest["passed"]),
        }
    if detail:
        approvals = conn.execute(
            "SELECT * FROM approvals WHERE app_id=? ORDER BY id", (row["id"],)
        ).fetchall()
        app["approvals"] = [dict(item) for item in approvals]
        versions = conn.execute(
            "SELECT id, version, status, created_by, created_at, published_at FROM app_versions "
            "WHERE app_id=? ORDER BY version DESC", (row["id"],)
        ).fetchall()
        app["versions"] = [dict(item) for item in versions]
        app["release_check"] = release_check_items(conn, row)
    return app


def _visible(user, app) -> bool:
    if user["role"] in ("admin", "platform_approver", "evaluator", "knowledge_ops"):
        return True
    if user["role"] in ("creator", "dept_approver"):
        return app["department"] == user["department"]
    if user["role"] == "doctor":
        return app["status"] == "published"
    return False


def _load(conn, app_id, user=None):
    app = conn.execute("SELECT * FROM apps WHERE id=?", (int(app_id),)).fetchone()
    if not app:
        raise common.ApiError(404, "not_found", "应用不存在")
    if user is not None and not _visible(user, app):
        raise common.ApiError(403, "forbidden", "无权访问该应用")
    return app


def list_apps(ctx):
    user, query = ctx["user"], ctx["query"]
    where, params = [], []
    if user["role"] in ("creator", "dept_approver"):
        where.append("department=?")
        params.append(user["department"])
    if query.get("status"):
        where.append("status=?")
        params.append(query["status"])
    if query.get("q"):
        where.append("(name LIKE ? OR code LIKE ?)")
        params.extend([f"%{query['q']}%", f"%{query['q']}%"])
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    limit, offset = common.pagination(query)
    total = ctx["conn"].execute(f"SELECT COUNT(*) AS c FROM apps{clause}", params).fetchone()["c"]
    rows = ctx["conn"].execute(
        f"SELECT * FROM apps{clause} ORDER BY id DESC LIMIT ? OFFSET ?", params + [limit, offset]
    ).fetchall()
    return 200, {"items": [_app_json(ctx["conn"], row) for row in rows], "total": total}


def create_app(ctx):
    conn, user, body = ctx["conn"], ctx["user"], ctx["body"]
    common.require(user, "app:create", "仅业务人员/管理员可创建应用")
    template_key = common.str_field(body.get("template_key"), "template_key", required=True)
    template = templates_mod.get_template(template_key)
    if not template:
        raise common.ApiError(400, "validation", "模板不存在")
    name = common.str_field(body.get("name"), "name", required=True)
    department = common.str_field(body.get("department"), "department", default=user["department"] or "公共")
    if user["role"] != "admin" and department != user["department"]:
        raise common.ApiError(403, "forbidden", "只能创建本部门应用")
    config = dict(template["config"])
    config["prompt_version"] = template["version"]
    config["template_version"] = template["version"]
    code = "APP-" + str(conn.execute("SELECT COUNT(*) AS c FROM apps").fetchone()["c"] + 1).zfill(4)
    app_id = conn.execute(
        """INSERT INTO apps(code, name, template_key, template_version, owner_id, department, status,
               risk_level, config, current_version, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (code, name, template_key, template["version"], user["id"], department, "draft",
         template["risk_level"], common.dumps(config), 0, db.iso(), db.iso()),
    ).lastrowid
    common.audit(conn, user["id"], "创建应用", "app", app_id, f"{name}（{template['name']}）")
    conn.commit()
    row = conn.execute("SELECT * FROM apps WHERE id=?", (app_id,)).fetchone()
    return 201, _app_json(conn, row, detail=True)


def get_app(ctx):
    app = _load(ctx["conn"], ctx["params"]["id"], ctx["user"])
    return 200, _app_json(ctx["conn"], app, detail=True)


def update_app(ctx):
    conn, user, body = ctx["conn"], ctx["user"], ctx["body"]
    app = _load(conn, ctx["params"]["id"], user)
    common.require(user, "app:edit", "仅创建者/管理员可编辑应用")
    if app["owner_id"] != user["id"] and user["role"] != "admin":
        raise common.ApiError(403, "forbidden", "仅应用创建者可编辑")
    if app["status"] not in ("draft", "testing"):
        raise common.ApiError(409, "conflict", "仅草稿/测试状态可编辑，已提交发布的应用不可改")
    config = _config(app)
    for key in ("model_policy", "knowledge_scope", "channels", "temperature",
                "memory_enabled", "memory_write_mode", "memory_search_mode"):
        if key in body:
            config[key] = body[key]
    if config.get("memory_write_mode") not in (None, "off", "session", "auto"):
        raise common.ApiError(400, "validation", "memory_write_mode 只能是 off/session/auto")
    if config.get("memory_search_mode") not in (None, "vector", "bigram"):
        raise common.ApiError(400, "validation", "memory_search_mode 只能是 vector/bigram")
    if config.get("model_policy") and not conn.execute(
            "SELECT 1 FROM model_policies WHERE key=?", (config["model_policy"],)).fetchone():
        raise common.ApiError(400, "validation", "模型策略不存在")
    if not isinstance(config.get("knowledge_scope"), list) or not config["knowledge_scope"]:
        raise common.ApiError(400, "validation", "knowledge_scope 必须是非空数组")
    conn.execute("UPDATE apps SET config=?, updated_at=? WHERE id=?",
                 (common.dumps(config), db.iso(), app["id"]))
    common.audit(conn, user["id"], "修改应用配置", "app", app["id"], "更新配置")
    conn.commit()
    return 200, _app_json(conn, conn.execute("SELECT * FROM apps WHERE id=?", (app["id"],)).fetchone(), detail=True)


def _session(conn, session_id, user):
    session = conn.execute("SELECT * FROM sessions WHERE id=?", (int(session_id),)).fetchone()
    if not session:
        raise common.ApiError(404, "not_found", "会话不存在")
    if session["user_id"] != user["id"] and user["role"] != "admin":
        raise common.ApiError(403, "forbidden", "无权访问该会话")
    return session


def create_session(ctx):
    conn, user = ctx["conn"], ctx["user"]
    app = _load(conn, ctx["params"]["id"], user)
    common.require(user, "app:trial", "无试跑权限")
    session_id = conn.execute(
        "INSERT INTO sessions(app_id, user_id, status, created_at) VALUES (?,?,?,?)",
        (app["id"], user["id"], "open", db.iso()),
    ).lastrowid
    common.audit(conn, user["id"], "创建调试会话", "session", session_id, f"应用 {app['id']}")
    conn.commit()
    return 201, {"session_id": session_id, "app_id": app["id"], "status": "open"}


def close_session(ctx):
    conn, user = ctx["conn"], ctx["user"]
    session = _session(conn, ctx["params"]["id"], user)
    if session["status"] == "closed":
        return 200, {"session_id": session["id"], "status": "closed", "memory_id": session["summary_memory_id"],
                     "note": "会话已关闭"}
    app = conn.execute("SELECT * FROM apps WHERE id=?", (session["app_id"],)).fetchone()
    config = _config(app)
    mode = config.get("memory_write_mode") or "off"
    runs = conn.execute("SELECT * FROM runs WHERE session_id=? ORDER BY id", (session["id"],)).fetchall()
    memory_id = None
    if mode == "session" and runs:
        memory_id = memory.write_summary(conn, app["id"], session["user_id"], runs, "session", mode)
        if memory_id:
            conn.execute("UPDATE runs SET memory_written=1 WHERE session_id=?", (session["id"],))
    conn.execute("UPDATE sessions SET status='closed', summary_memory_id=?, closed_at=? WHERE id=?",
                 (memory_id, db.iso(), session["id"]))
    common.audit(conn, user["id"], "结束调试会话", "session", session["id"],
                 f"模式={mode} runs={len(runs)} memory={memory_id}")
    conn.commit()
    return 200, {"session_id": session["id"], "status": "closed", "write_mode": mode,
                 "runs": len(runs), "memory_id": memory_id}


def list_runs(ctx):
    common.require(ctx["user"], "metrics:read")
    query = ctx["query"]
    where, params = [], []
    if query.get("app_id"):
        where.append("app_id=?")
        params.append(common.int_field(query["app_id"], "app_id", minimum=1))
    if query.get("session_id"):
        where.append("session_id=?")
        params.append(common.int_field(query["session_id"], "session_id", minimum=1))
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    limit, offset = common.pagination(query)
    rows = ctx["conn"].execute(
        f"""SELECT r.*, a.name AS app_name FROM runs r LEFT JOIN apps a ON a.id=r.app_id
            {clause} ORDER BY r.id DESC LIMIT ? OFFSET ?""", params + [limit, offset]).fetchall()
    return 200, {"items": [dict(row) for row in rows]}


def trial(ctx):
    conn, user, body = ctx["conn"], ctx["user"], ctx["body"]
    app = _load(conn, ctx["params"]["id"], user)
    common.require(user, "app:trial", "无试跑权限")
    if app["status"] == "disabled":
        raise common.ApiError(409, "conflict", "应用已停用")
    query = common.str_field(body.get("query") or body.get("content"), "query", required=True)
    if len(query) > 4000:
        raise common.ApiError(400, "validation", "输入过长（≤4000 字）")
    session_id = body.get("session_id")
    if session_id:
        session = _session(conn, session_id, user)
        if session["app_id"] != app["id"]:
            raise common.ApiError(400, "validation", "session 与应用不匹配")
        if session["status"] == "closed":
            raise common.ApiError(409, "conflict", "会话已结束，请新建会话")
        session_id = session["id"]
    else:
        session_id = conn.execute(
            "INSERT INTO sessions(app_id, user_id, status, created_at) VALUES (?,?,?,?)",
            (app["id"], user["id"], "open", db.iso()),
        ).lastrowid
    result = engine.generate(conn, app, query, user["department"] or "", user_id=user["id"])
    run_id = conn.execute(
        """INSERT INTO runs(app_id, session_id, user_id, input, output, status, degraded, tokens, cost,
               latency_ms, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (app["id"], session_id, user["id"], query, result["output"], "succeeded",
         1 if result["degraded"] else 0, result["tokens"], result["cost"], result["latency_ms"], db.iso()),
    ).lastrowid
    config = _config(app)
    write_mode = config.get("memory_write_mode") or "off"
    if write_mode == "auto":
        memory_id = memory.write_summary(conn, app["id"], user["id"],
                                        [{"input": query, "output": result["output"]}], "run", "auto")
        if memory_id:
            conn.execute("UPDATE runs SET memory_written=1 WHERE id=?", (run_id,))
            result["trace"].append({"type": "memory", "name": "自动写入摘要", "status": "succeeded",
                                    "detail": f"运行后自动写入摘要记忆 #{memory_id}", "latency_ms": 5})
            result["memory"]["auto_written"] = True
            result["memory"]["memory_id"] = memory_id
        else:
            result["memory"]["auto_written"] = False
    if app["status"] == "draft":
        conn.execute("UPDATE apps SET status='testing', updated_at=? WHERE id=?", (db.iso(), app["id"]))
    common.audit(conn, user["id"], "试跑应用", "app", app["id"],
                 f"{len(query)} 字，降级={result['degraded']}，run={run_id}")
    conn.commit()
    return 200, {
        "app": {"id": app["id"], "name": app["name"], "status": conn.execute(
            "SELECT status FROM apps WHERE id=?", (app["id"],)).fetchone()["status"]},
        "run_id": run_id,
        "session_id": session_id,
        "memory_write_mode": write_mode,
        **result,
    }


def release_check_items(conn, app) -> dict:
    config = _config(app)
    template = templates_mod.get_template(app["template_key"])
    items = []
    items.append({"key": "template", "label": "模板可用", "ok": bool(template),
                  "detail": f"{app['template_key']} v{app['template_version']}"})
    scope = config.get("knowledge_scope") or []
    items.append({"key": "scope", "label": "知识范围已配置", "ok": bool(scope), "detail": ",".join(scope)})
    has_docs = knowledge.scope_has_docs(conn, scope) if scope else False
    items.append({"key": "knowledge", "label": "范围内存在已审核且生效知识", "ok": has_docs,
                  "detail": "存在可用知识" if has_docs else "无可用知识"})
    latest = _latest_eval(conn, app["id"])
    ok_eval = bool(latest and latest["passed"] and latest["gate_status"] == "passed")
    items.append({"key": "eval", "label": "评测门禁通过", "ok": ok_eval,
                  "detail": (f"run #{latest['id']} {latest['gate_status']} 阈值 {latest['threshold']}"
                             if latest else "尚未评测")})
    high_events = conn.execute(
        "SELECT COUNT(*) AS c FROM safety_events WHERE app_id=? AND severity='high'", (app["id"],)
    ).fetchone()["c"]
    items.append({"key": "safety", "label": "无未处置高风险安全事件", "ok": high_events == 0,
                  "detail": f"{high_events} 个高风险事件"})
    ready = all(item["ok"] for item in items)
    return {"items": items, "ready": ready}


def release_check(ctx):
    app = _load(ctx["conn"], ctx["params"]["id"], ctx["user"])
    return 200, release_check_items(ctx["conn"], app)


def submit(ctx):
    conn, user = ctx["conn"], ctx["user"]
    app = _load(conn, ctx["params"]["id"], user)
    common.require(user, "app:submit", "无提交发布权限")
    if app["owner_id"] != user["id"] and user["role"] != "admin":
        raise common.ApiError(403, "forbidden", "仅应用创建者可提交发布")
    if app["status"] not in ("draft", "testing"):
        raise common.ApiError(409, "conflict", f"当前状态不可提交（{app['status']}）")
    check = release_check_items(conn, app)
    if not check["ready"]:
        raise common.ApiError(409, "release_blocked", "发布检查未通过", check["items"])
    conn.execute("UPDATE apps SET status='pending_dept', updated_at=? WHERE id=?", (db.iso(), app["id"]))
    approval_id = conn.execute(
        "INSERT INTO approvals(app_id, kind, status, created_at) VALUES (?,?,?,?)",
        (app["id"], "dept", "pending", db.iso()),
    ).lastrowid
    common.audit(conn, user["id"], "提交发布", "app", app["id"], f"进入科室审批（approval #{approval_id}）")
    conn.commit()
    return 200, {"app_id": app["id"], "status": "pending_dept", "approval_id": approval_id}


def list_approvals(ctx):
    user, query = ctx["user"], ctx["query"]
    if user["role"] not in ("admin", "dept_approver", "platform_approver"):
        raise common.ApiError(403, "forbidden", "无审批权限")
    where, params = [], []
    if user["role"] == "dept_approver":
        where.extend(["a.kind='dept'", "app.department=?"])
        params.append(user["department"])
    elif user["role"] == "platform_approver":
        where.append("a.kind='platform'")
    if query.get("status"):
        where.append("a.status=?")
        params.append(query["status"])
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    rows = ctx["conn"].execute(
        f"""SELECT a.*, app.name AS app_name, app.department, app.code AS app_code
            FROM approvals a JOIN apps app ON app.id=a.app_id {clause} ORDER BY a.id DESC""",
        params,
    ).fetchall()
    return 200, {"items": [dict(row) for row in rows]}


def decide(ctx):
    conn, user, body = ctx["conn"], ctx["user"], ctx["body"]
    approval_id = int(ctx["params"]["id"])
    approval = conn.execute("SELECT * FROM approvals WHERE id=?", (approval_id,)).fetchone()
    if not approval:
        raise common.ApiError(404, "not_found", "审批不存在")
    if approval["status"] != "pending":
        raise common.ApiError(409, "conflict", "该审批已处理")
    app = conn.execute("SELECT * FROM apps WHERE id=?", (approval["app_id"],)).fetchone()
    if approval["kind"] == "dept":
        common.require(user, "approval:dept", "仅科室审批人可处理科室审批")
        if user["role"] == "dept_approver" and app["department"] != user["department"]:
            raise common.ApiError(403, "forbidden", "只能审批本部门应用")
    else:
        common.require(user, "approval:platform", "仅平台审批人可处理平台审批")
    decision = common.str_field(body.get("decision"), "decision", required=True)
    if decision not in ("approve", "reject"):
        raise common.ApiError(400, "validation", "decision 只能是 approve/reject")
    comment = common.str_field(body.get("comment"), "comment", default="")
    now = db.iso()
    conn.execute(
        "UPDATE approvals SET status=?, reviewer_id=?, comment=?, decided_at=? WHERE id=?",
        ("approved" if decision == "approve" else "rejected", user["id"], comment, now, approval_id),
    )
    if decision == "reject":
        conn.execute("UPDATE apps SET status='draft', updated_at=? WHERE id=?", (now, app["id"]))
        common.audit(conn, user["id"], "拒绝发布", "app", app["id"], comment)
        conn.commit()
        return 200, {"status": "draft", "decision": "rejected"}
    if approval["kind"] == "dept":
        next_id = conn.execute(
            "INSERT INTO approvals(app_id, kind, status, created_at) VALUES (?,?,?,?)",
            (app["id"], "platform", "pending", now),
        ).lastrowid
        conn.execute("UPDATE apps SET status='pending_platform', updated_at=? WHERE id=?", (now, app["id"]))
        common.audit(conn, user["id"], "科室审批通过", "app", app["id"], f"进入平台审批（#{next_id}）")
        conn.commit()
        return 200, {"status": "pending_platform", "next_approval_id": next_id}
    # platform approve -> publish
    result = publish(conn, app, user)
    common.audit(conn, user["id"], "平台审批通过并发布", "app", app["id"], f"版本 v{result['version']}")
    conn.commit()
    return 200, result


def publish(conn, app, user) -> dict:
    config = _config(app)
    template = templates_mod.get_template(app["template_key"])
    scope = config.get("knowledge_scope") or []
    docs = conn.execute("SELECT * FROM knowledge_docs WHERE status='approved'").fetchall()
    knowledge_versions = []
    for doc in docs:
        doc_scope = common.loads(doc["scope"], []) or []
        if set(scope) & set(doc_scope) or "公共" in doc_scope:
            knowledge_versions.append({"id": doc["id"], "title": doc["title"], "version": doc["version"]})
    latest_eval = _latest_passed_eval(conn, app["id"])
    version = conn.execute(
        "SELECT COALESCE(MAX(version), 0) + 1 AS v FROM app_versions WHERE app_id=?", (app["id"],)
    ).fetchone()["v"]
    snapshot = {
        "app_id": app["id"],
        "config": config,
        "template_key": app["template_key"],
        "template_version": app["template_version"],
        "prompt_version": template["version"] if template else None,
        "model_policy": config.get("model_policy"),
        "knowledge_versions": knowledge_versions,
        "eval_run_id": latest_eval["id"] if latest_eval else None,
        "published_by": user["id"],
        "published_at": db.iso(),
    }
    conn.execute(
        """INSERT INTO app_versions(app_id, version, snapshot, status, created_by, created_at, published_at)
           VALUES (?,?,?,?,?,?,?)""",
        (app["id"], version, common.dumps(snapshot), "published", user["id"], db.iso(), db.iso()),
    )
    conn.execute("UPDATE apps SET status='published', current_version=?, updated_at=? WHERE id=?",
                 (version, db.iso(), app["id"]))
    return {"status": "published", "version": version, "snapshot": snapshot}


def disable(ctx):
    conn, user = ctx["conn"], ctx["user"]
    app = _load(conn, ctx["params"]["id"], user)
    common.require(user, "approval:platform", "仅平台审批/管理员可停用")
    conn.execute("UPDATE apps SET status='disabled', updated_at=? WHERE id=?", (db.iso(), app["id"]))
    common.audit(conn, user["id"], "停用应用", "app", app["id"], "")
    conn.commit()
    return 200, {"status": "disabled"}


def rollback(ctx):
    conn, user, body = ctx["conn"], ctx["user"], ctx["body"]
    app = _load(conn, ctx["params"]["id"], user)
    common.require(user, "approval:platform", "仅平台审批/管理员可回滚")
    version = common.int_field(body.get("version"), "version", minimum=1)
    target = conn.execute(
        "SELECT * FROM app_versions WHERE app_id=? AND version=?", (app["id"], version)
    ).fetchone()
    if not target:
        raise common.ApiError(404, "not_found", "目标版本不存在")
    snapshot = common.loads(target["snapshot"], {}) or {}
    config = snapshot.get("config") or _config(app)
    conn.execute(
        "UPDATE apps SET config=?, current_version=?, status='published', updated_at=? WHERE id=?",
        (common.dumps(config), version, db.iso(), app["id"]),
    )
    common.audit(conn, user["id"], "回滚应用", "app", app["id"], f"回滚到 v{version}")
    conn.commit()
    return 200, {"status": "published", "current_version": version}


def versions(ctx):
    app = _load(ctx["conn"], ctx["params"]["id"], ctx["user"])
    rows = ctx["conn"].execute(
        "SELECT * FROM app_versions WHERE app_id=? ORDER BY version DESC", (app["id"],)
    ).fetchall()
    items = []
    for row in rows:
        item = dict(row)
        item["snapshot"] = common.loads(item["snapshot"], {}) or {}
        items.append(item)
    return 200, {"items": items, "total": len(items)}


def feedback(ctx):
    """试跑反馈：有用记录审计；无用进入 BadCase 队列（FR-010）。"""
    conn, user, body = ctx["conn"], ctx["user"], ctx["body"]
    app = _load(conn, ctx["params"]["id"], user)
    common.require(user, "app:trial", "无反馈权限")
    helpful = bool(body.get("helpful"))
    question = common.str_field(body.get("question"), "question", default="")
    output = common.str_field(body.get("output"), "output", default="")
    reason = common.str_field(body.get("reason"), "reason", default="quality")
    comment = common.str_field(body.get("comment"), "comment", default="")
    badcase_id = None
    if not helpful:
        badcase_id = conn.execute(
            "INSERT INTO badcases(app_id, source, question, output, category, severity, status, created_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (app["id"], user["id"], question, output, reason, "medium", "open", db.iso()),
        ).lastrowid
    common.audit(conn, user["id"], "试跑反馈", "app", app["id"],
                 f"helpful={helpful} reason={reason} comment={comment[:60]}")
    conn.commit()
    return 200, {"ok": True, "helpful": helpful, "badcase_id": badcase_id}


ROUTES = [
    ("GET", re.compile(r"^/api/apps$"), list_apps),
    ("POST", re.compile(r"^/api/apps$"), create_app),
    ("GET", re.compile(r"^/api/apps/(?P<id>\d+)$"), get_app),
    ("PUT", re.compile(r"^/api/apps/(?P<id>\d+)$"), update_app),
    ("POST", re.compile(r"^/api/apps/(?P<id>\d+)/trial$"), trial),
    ("POST", re.compile(r"^/api/apps/(?P<id>\d+)/feedback$"), feedback),
    ("POST", re.compile(r"^/api/apps/(?P<id>\d+)/sessions$"), create_session),
    ("POST", re.compile(r"^/api/sessions/(?P<id>\d+)/close$"), close_session),
    ("GET", re.compile(r"^/api/runs$"), list_runs),
    ("GET", re.compile(r"^/api/apps/(?P<id>\d+)/release-check$"), release_check),
    ("POST", re.compile(r"^/api/apps/(?P<id>\d+)/submit$"), submit),
    ("POST", re.compile(r"^/api/apps/(?P<id>\d+)/disable$"), disable),
    ("POST", re.compile(r"^/api/apps/(?P<id>\d+)/rollback$"), rollback),
    ("GET", re.compile(r"^/api/apps/(?P<id>\d+)/versions$"), versions),
    ("GET", re.compile(r"^/api/approvals$"), list_approvals),
    ("POST", re.compile(r"^/api/approvals/(?P<id>\d+)/decide$"), decide),
]
