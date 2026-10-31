"""应用执行引擎：模板生成 + 知识检索 + 安全拦截 + 模型网关。"""
from __future__ import annotations

import json
import re

import common
import knowledge
import models
import safety
import templates as templates_mod

DISCLAIMER = safety.DISCLAIMER


def _app_config(app) -> dict:
    return common.loads(app["config"], {}) or {}


def generate(conn, app, query: str, department: str = "") -> dict:
    template = templates_mod.get_template(app["template_key"])
    if not template:
        raise common.ApiError(400, "template_missing", "应用关联模板不存在")
    config = _app_config(app)
    policy = config.get("model_policy") or "precise"
    scope = config.get("knowledge_scope") or template["config"].get("knowledge_scope", [])
    citations: list[dict] = []
    blocked = False
    handoff = False

    if app["template_key"] == "med-knowledge":
        hits = knowledge.search(conn, query, scope, limit=3)
        if hits:
            citations = hits
            lines = [f"【{idx + 1}】{hit['excerpt']}" for idx, hit in enumerate(hits[:3])]
            answer = "根据院内已审核知识：\n" + "\n".join(lines)
        else:
            answer = "未找到明确依据。建议人工检索或咨询专科医生，AI 不提供确定性结论。"
    elif app["template_key"] == "med-qc":
        defects = []
        for keyword, vtype, severity, basis, suggestion in templates_mod.QC_RULES:
            if keyword not in (query or ""):
                defects.append({
                    "type": vtype,
                    "severity": severity,
                    "basis": basis,
                    "suggestion": suggestion,
                    "location": f"未找到“{keyword}”相关记录",
                })
        score = max(0, 100 - 15 * len(defects))
        answer = json.dumps({
            "score": score,
            "defects": defects,
            "summary": f"共发现 {len(defects)} 项缺陷，需质控人员确认。",
            "disclaimer": DISCLAIMER,
        }, ensure_ascii=False)
    else:
        raise common.ApiError(400, "template_missing", "不支持的模板")

    gateway = models.call_gateway(conn, app["id"], policy, query)
    if gateway.get("ok"):
        versions = {
            "app_version": app["current_version"],
            "template_key": app["template_key"],
            "template_version": app["template_version"],
            "prompt_version": template["version"],
            "model_policy": policy,
            "model": gateway.get("model_key"),
            "knowledge_versions": [f"{c['title']}·v{c['version']}" for c in citations],
        }
        latency = gateway.get("latency_ms", 0)
        tokens = gateway.get("tokens", 0)
        cost = gateway.get("cost", 0)
        degraded = gateway.get("degraded", False)
    else:
        # 故障安全：模型不可用时不得伪造结论
        answer = "模型服务当前不可用，无法生成可靠结论。已提示人工处理，请稍后重试或联系医生。"
        degraded = True
        handoff = True
        versions = {"app_version": app["current_version"], "template_key": app["template_key"],
                    "template_version": app["template_version"], "prompt_version": template["version"],
                    "model_policy": policy, "model": None, "knowledge_versions": []}
        latency, tokens, cost = 0, 0, 0
        conn.execute(
            "INSERT INTO safety_events(app_id, run_id, category, severity, action, detail, created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (app["id"], None, "model_unavailable", "high", "handoff", "模型不可用，按故障安全转人工", common.db_iso()),
        )

    enforced = safety.enforce(conn, app["id"], answer)
    if enforced["blocked"]:
        answer = enforced["output"]
        blocked = True
        handoff = True
    if DISCLAIMER not in answer:
        answer = answer.rstrip() + "\n\n" + DISCLAIMER
    conn.commit()
    return {
        "output": answer,
        "citations": citations,
        "disclaimer": DISCLAIMER,
        "versions": versions,
        "degraded": bool(degraded or blocked),
        "safety": {"blocked": blocked, "handoff": handoff, "categories": enforced.get("categories", [])},
        "latency_ms": latency,
        "tokens": tokens,
        "cost": cost,
        "model": gateway,
    }
