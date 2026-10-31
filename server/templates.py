"""两个 POC 模板：医学知识问答、病历质控。"""
from __future__ import annotations

import re

import common

DISCLAIMER = "本结果为 AI 辅助信息，不构成诊疗建议；须由具备资质的医生复核确认。"

TEMPLATES = {
    "med-knowledge": {
        "key": "med-knowledge",
        "name": "医学知识问答",
        "version": 1,
        "risk_level": "low",
        "description": "基于院内已审核指南/制度/说明书的检索问答，返回可核验引用，不输出诊断结论。",
        "eval_threshold": 0.85,
        "config": {
            "model_policy": "precise",
            "knowledge_scope": ["心血管内科", "公共"],
            "channels": ["web", "miniprogram"],
            "output": ["answer", "citations", "disclaimer"],
            "temperature": 0.1,
            "risk_level": "low",
            "forbidden": ["诊断", "处方", "剂量"],
        },
        "prompt_system": (
            "你是院内医学知识助手，仅依据已审核知识回答。规则：1) 每个关键结论标注引用编号；"
            "2) 检索不足时回答“未找到明确依据”，不得编造；3) 不给出诊断、处方或剂量；"
            "4) 末尾附免责声明。"
        ),
        "prompt_user": "问题：{{query}}\n科室：{{department}}\n知识范围：{{scope}}",
        "output_schema": {
            "type": "object",
            "required": ["answer", "citations", "disclaimer"],
            "properties": {
                "answer": {"type": "string"},
                "citations": {"type": "array"},
                "disclaimer": {"type": "string"},
            },
        },
    },
    "med-qc": {
        "key": "med-qc",
        "name": "病历质控助手",
        "version": 1,
        "risk_level": "medium",
        "description": "依据病历书写规范与院内制度检查缺陷，输出缺陷类型/依据/定位/建议，只读不改病历。",
        "eval_threshold": 0.70,
        "config": {
            "model_policy": "precise",
            "knowledge_scope": ["病案质控", "公共"],
            "channels": ["web"],
            "output": ["score", "defects", "disclaimer"],
            "temperature": 0.1,
            "risk_level": "medium",
            "forbidden": ["诊断", "处方"],
        },
        "prompt_system": (
            "你是病历质控助手。依据规范输出 JSON：{score, defects:[{type,severity,basis,location,suggestion}]}。"
            "只输出有依据的缺陷；不确定标记“建议人工复核”；不修改病历；不给诊断结论。"
        ),
        "prompt_user": "病历内容：{{content}}\n科室：{{department}}",
        "output_schema": {
            "type": "object",
            "required": ["score", "defects", "disclaimer"],
        },
    },
}

TEMPLATES["med-report"] = {
    "key": "med-report",
    "name": "报告初稿助手",
    "version": 1,
    "risk_level": "medium",
    "description": "根据检查类型与结构化所见生成报告初稿（所见/印象/建议），医生编辑签名后生效。",
    "eval_threshold": 0.75,
    "config": {
        "model_policy": "private",
        "knowledge_scope": ["公共", "医学影像"],
        "channels": ["web"],
        "output": ["findings", "impression", "recommendation", "missing_fields", "disclaimer"],
        "temperature": 0.3,
        "risk_level": "medium",
        "memory_enabled": False,
        "memory_write_mode": "off",
        "memory_search_mode": "vector",
    },
    "prompt_system": (
        "你是报告初稿助手。严格按院内模板输出 JSON：{findings, impression, recommendation, missing_fields, disclaimer}。"
        "只描述输入中存在的信息，不添加未提供的阳性/阴性结果；不给出确诊结论；缺失字段列入 missing_fields。"
    ),
    "prompt_user": "检查类型：{{exam_type}}\n结构化所见：{{findings}}\n模板：{{template_name}}",
    "output_schema": {
        "type": "object",
        "required": ["findings", "impression", "recommendation", "missing_fields", "disclaimer"],
    },
}

QC_RULES = [
    ("既往史", "完整性", "高", "入院记录既往史缺失", "补写既往史"),
    ("过敏史", "完整性", "高", "过敏史缺失", "补写过敏史"),
    ("主诉", "完整性", "中", "主诉未按“症状+时长”书写", "规范主诉"),
    ("病程记录", "时限性", "中", "病程记录间隔超时", "补记病程"),
    ("签名", "合法性", "高", "缺少医师签名", "补签"),
    ("手术记录", "一致性", "中", "手术记录与病程不一致", "核对并修正"),
]


def template_list(ctx):
    items = []
    for template in TEMPLATES.values():
        item = dict(template)
        item.pop("prompt_system", None)
        item.pop("prompt_user", None)
        items.append(item)
    return 200, {"items": items, "total": len(items)}


def template_detail(ctx, key):
    template = TEMPLATES.get(key)
    if not template:
        raise common.ApiError(404, "not_found", "模板不存在")
    data = dict(template)
    data["prompt_system_preview"] = template["prompt_system"][:200]
    return 200, data


def get_template(key: str) -> dict | None:
    return TEMPLATES.get(key)


ROUTES = [
    ("GET", re.compile(r"^/api/templates$"), template_list),
    ("GET", re.compile(r"^/api/templates/(?P<key>[a-z0-9-]+)$"), template_detail),
]
