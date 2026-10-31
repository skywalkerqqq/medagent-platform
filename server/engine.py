"""应用执行引擎：模板生成 + 知识检索 + 安全拦截 + 模型网关。"""
from __future__ import annotations

import json
import re

import common
import knowledge
import memory
import models
import safety
import templates as templates_mod

DISCLAIMER = safety.DISCLAIMER


def _app_config(app) -> dict:
    return common.loads(app["config"], {}) or {}


def generate(conn, app, query: str, department: str = "", user_id: str | None = None) -> dict:
    template = templates_mod.get_template(app["template_key"])
    if not template:
        raise common.ApiError(400, "template_missing", "应用关联模板不存在")
    config = _app_config(app)
    policy = config.get("model_policy") or "precise"
    scope = config.get("knowledge_scope") or template["config"].get("knowledge_scope", [])
    citations: list[dict] = []
    blocked = False
    handoff = False
    memory_hits: list[dict] = []
    memory_step = None

    if app["template_key"] == "med-knowledge":
        hits = knowledge.search(conn, query, scope, limit=3)
        faq_hits = knowledge.search_faqs(conn, query, scope, limit=2)
        citations = []
        lines = []
        for hit in hits:
            citations.append(hit)
            lines.append(f"【{len(lines) + 1}】{hit['excerpt']}")
        for faq in faq_hits:
            citations.append({
                "doc_id": 0, "faq_id": faq["faq_id"], "title": faq["title"],
                "source": faq["source"], "version": 1, "excerpt": faq["answer"],
                "citation": faq["citation"], "score": faq["score"],
            })
            lines.append(f"【FAQ】{faq['title']}：{faq['answer'][:120]}")
        if lines:
            answer = "根据院内已审核知识与 FAQ：\n" + "\n".join(lines)
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
    elif app["template_key"] == "med-report":
        missing = []
        lowered = (query or "").lower()
        if "mm" not in lowered and "cm" not in lowered:
            missing.append("病灶大小")
        if "部位" not in (query or "") and "肺" not in (query or "") and "肝" not in (query or ""):
            missing.append("检查部位")
        answer = json.dumps({
            "findings": (query or "").strip() or "未见结构化所见",
            "impression": "考虑相关影像学改变，建议结合临床",
            "recommendation": "建议随访复查" if missing else "建议结合临床进一步评估",
            "missing_fields": missing,
            "disclaimer": DISCLAIMER,
        }, ensure_ascii=False)
    else:
        raise common.ApiError(400, "template_missing", "不支持的模板")

    # 记忆摘要使用“干净回答”（注入记忆前），避免摘要嵌套上一次的记忆内容
    core_answer = answer
    if config.get("memory_enabled") and user_id:
        search_mode = config.get("memory_search_mode") or "vector"
        memory_hits = memory.retrieve(conn, app["id"], user_id, query, mode=search_mode)
        if memory_hits:
            memory.mark_used(conn, [item["id"] for item in memory_hits])
            block = "\n".join(f"- {item['content']}" for item in memory_hits)
            answer = f"【结合历史记忆】\n{block}\n\n{answer}"
            memory_step = {"type": "memory", "name": "记忆注入", "status": "succeeded",
                           "detail": f"注入 {len(memory_hits)} 条相关记忆", "latency_ms": 6}
        else:
            memory_step = {"type": "memory", "name": "记忆注入", "status": "empty",
                           "detail": "无相关记忆", "latency_ms": 4}

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
    trace = [
        {"type": "template", "name": "加载模板", "status": "succeeded",
         "detail": f"{app['template_key']} v{app['template_version']} · 提示词 v{template['version']}", "latency_ms": 4},
    ]
    if memory_step:
        trace.append(memory_step)
    if app["template_key"] == "med-knowledge":
        trace.append({
            "type": "rag", "name": "知识检索", "status": "succeeded" if citations else "empty",
            "detail": f"命中 {len(citations)} 条已审核知识" if citations else "未命中可用知识（拒答，不编造）",
            "latency_ms": 18,
        })
    else:
        trace.append({
            "type": "rule", "name": "质控规则检查", "status": "succeeded",
            "detail": "规则+结构化校验完成", "latency_ms": 12,
        })
    trace.append({
        "type": "model", "name": "模型调用", "status": "degraded" if degraded else ("failed" if not gateway.get("ok") else "succeeded"),
        "detail": (f"{gateway.get('model_key') or '不可用'} · 策略 {policy}"
                   + (" · 降级" if degraded else "")),
        "latency_ms": latency,
    })
    trace.append({
        "type": "safety", "name": "安全检查",
        "status": "blocked" if blocked else "succeeded",
        "detail": ("命中禁止项，已转人工" if blocked else "通过：无诊断/处方/不安全建议"),
        "latency_ms": 3,
    })
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
        "trace": trace,
        "summary_text": core_answer[:300],
        "memory": {"enabled": bool(config.get("memory_enabled")),
                   "injected": len(memory_hits),
                   "search_mode": config.get("memory_search_mode") or "vector",
                   "use_count": sum(item.get("use_count", 0) for item in memory_hits)},
    }
