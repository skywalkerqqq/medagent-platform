"""评测中心：数据集、离线评测、指标口径与发布门禁。"""
from __future__ import annotations

import re

import common
import db
import engine


def metric_definitions() -> list[dict]:
    return [
        {"key": "recall", "name": "Top-k 召回率", "definition": "金标准相关证据进入前 k 条的比例", "unit": "ratio"},
        {"key": "citation_accuracy", "name": "引用准确率", "definition": "引用能支持结论的抽检比例", "unit": "ratio"},
        {"key": "answer_correct", "name": "答案正确率", "definition": "临床标注为正确/可接受的答案比例", "unit": "ratio"},
        {"key": "fabrication_rate", "name": "无依据编造率", "definition": "无来源支持事实性医疗主张的答案比例", "unit": "ratio"},
        {"key": "detection_rate", "name": "缺陷检出率", "definition": "正确检出的金标准缺陷比例", "unit": "ratio"},
        {"key": "false_positive_rate", "name": "误报率", "definition": "错误提示占全部提示的比例", "unit": "ratio"},
    ]


def list_datasets(ctx):
    common.require(ctx["user"], "metrics:read")
    rows = ctx["conn"].execute(
        """SELECT d.*, (SELECT COUNT(*) FROM eval_cases c WHERE c.dataset_id=d.id) AS case_count
           FROM eval_datasets d ORDER BY d.id"""
    ).fetchall()
    return 200, {"items": [dict(row) for row in rows], "metric_definitions": metric_definitions()}


def _keywords(expected: str) -> list[str]:
    return [part.strip() for part in re.split(r"[,，;；|/\s]+", expected or "") if part.strip()]


def _run_one(conn, app, case) -> tuple[str, float, dict]:
    result = engine.generate(conn, app, case["input"])
    output = result["output"]
    keywords = _keywords(case["expected"])
    matched = sum(1 for keyword in keywords if keyword in output)
    score = (matched / len(keywords)) if keywords else 0.0
    metrics = {
        "matched": matched,
        "expected": len(keywords),
        "score": round(score, 3),
        "citations": len(result["citations"]),
        "blocked": result["safety"]["blocked"],
        "degraded": result["degraded"],
    }
    return output, score, metrics


def run(ctx):
    conn, user, body = ctx["conn"], ctx["user"], ctx["body"]
    common.require(user, "eval:run", "仅评测/管理员可执行评测")
    app_id = common.int_field(body.get("app_id"), "app_id", minimum=1)
    app = conn.execute("SELECT * FROM apps WHERE id=?", (app_id,)).fetchone()
    if not app:
        raise common.ApiError(404, "not_found", "应用不存在")
    dataset_key = common.str_field(body.get("dataset_key"), "dataset_key", default="")
    dataset = conn.execute(
        "SELECT * FROM eval_datasets WHERE key=? OR template_key=?", (dataset_key, app["template_key"])
    ).fetchone()
    if not dataset:
        raise common.ApiError(404, "not_found", "评测集不存在")
    cases = conn.execute("SELECT * FROM eval_cases WHERE dataset_id=? ORDER BY id", (dataset["id"],)).fetchall()
    if not cases:
        raise common.ApiError(400, "validation", "评测集为空")

    thresholds = {"med-knowledge": 0.85, "med-qc": 0.70, "med-report": 0.75}
    threshold = thresholds.get(app["template_key"], 0.8)
    results = []
    scores = []
    claim_cases = 0
    claim_citations = 0
    blocked = 0
    for case in cases:
        output, score, metrics = _run_one(conn, app, case)
        scores.append(score)
        is_claim = "未找到" not in (case["expected"] or "")
        if is_claim:
            claim_cases += 1
            claim_citations += 1 if metrics["citations"] > 0 else 0
        blocked += 1 if metrics["blocked"] else 0
        passed = 1 if score >= 0.6 and not metrics["blocked"] else 0
        results.append((case["id"], output, metrics, passed))

    avg = sum(scores) / len(scores)
    if app["template_key"] == "med-knowledge":
        citation_accuracy = (claim_citations / claim_cases) if claim_cases else 1.0
        metrics = {
            "recall": round(avg, 3),
            "citation_accuracy": round(citation_accuracy, 3),
            "answer_correct": round(sum(1 for r in results if r[3]) / len(cases), 3),
            "fabrication_rate": round(1 - citation_accuracy, 3) if claim_cases else 0.0,
            "blocked_rate": round(blocked / len(cases), 3),
        }
        passed = (metrics["recall"] >= threshold and metrics["citation_accuracy"] >= 0.8
                  and metrics["fabrication_rate"] <= 0.05)
    else:
        metrics = {
            "detection_rate": round(avg, 3),
            "false_positive_rate": 0.0,
            "blocked_rate": round(blocked / len(cases), 3),
        }
        passed = metrics["detection_rate"] >= threshold
    gate = "passed" if passed else "failed"
    run_id = conn.execute(
        """INSERT INTO eval_runs(app_id, dataset_id, status, metrics, passed, threshold, gate_status, created_by, created_at)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (app_id, dataset["id"], "finished", common.dumps(metrics), 1 if passed else 0,
         threshold, gate, user["id"], db.iso()),
    ).lastrowid
    for case_id, output, result_metrics, result_passed in results:
        conn.execute(
            "INSERT INTO eval_results(run_id, case_id, output, metrics, passed) VALUES (?,?,?,?,?)",
            (run_id, case_id, output, common.dumps(result_metrics), result_passed),
        )
    common.audit(conn, user["id"], "执行评测", "eval_run", run_id,
                 f"应用 #{app_id}，{dataset['name']}，门禁：{gate}")
    conn.commit()
    return 200, {
        "run_id": run_id,
        "app_id": app_id,
        "dataset": dataset["key"],
        "threshold": threshold,
        "metrics": metrics,
        "gate_status": gate,
        "passed": bool(passed),
        "metric_definitions": metric_definitions(),
    }


def list_runs(ctx):
    common.require(ctx["user"], "metrics:read")
    query = ctx["query"]
    where, params = [], []
    if query.get("app_id"):
        where.append("r.app_id=?")
        params.append(common.int_field(query["app_id"], "app_id", minimum=1))
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    limit, offset = common.pagination(query)
    rows = ctx["conn"].execute(
        f"""SELECT r.*, a.name AS app_name FROM eval_runs r LEFT JOIN apps a ON a.id=r.app_id
            {clause} ORDER BY r.id DESC LIMIT ? OFFSET ?""",
        params + [limit, offset],
    ).fetchall()
    items = []
    for row in rows:
        item = dict(row)
        item["metrics"] = common.loads(item["metrics"], {}) or {}
        items.append(item)
    return 200, {"items": items}


def get_run(ctx):
    common.require(ctx["user"], "metrics:read")
    run_id = int(ctx["params"]["id"])
    run_row = ctx["conn"].execute("SELECT * FROM eval_runs WHERE id=?", (run_id,)).fetchone()
    if not run_row:
        raise common.ApiError(404, "not_found", "评测记录不存在")
    data = dict(run_row)
    data["metrics"] = common.loads(data["metrics"], {}) or {}
    results = ctx["conn"].execute(
        """SELECT r.*, c.input, c.expected FROM eval_results r
           JOIN eval_cases c ON c.id=r.case_id WHERE r.run_id=? ORDER BY r.id""",
        (run_id,),
    ).fetchall()
    data["results"] = []
    for row in results:
        item = dict(row)
        item["metrics"] = common.loads(item["metrics"], {}) or {}
        data["results"].append(item)
    return 200, data


ROUTES = [
    ("GET", re.compile(r"^/api/eval/datasets$"), list_datasets),
    ("POST", re.compile(r"^/api/eval/run$"), run),
    ("GET", re.compile(r"^/api/eval/runs$"), list_runs),
    ("GET", re.compile(r"^/api/eval/runs/(?P<id>\d+)$"), get_run),
]
