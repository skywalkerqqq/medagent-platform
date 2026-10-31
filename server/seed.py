"""演示种子数据：用户/模板/知识/模型/评测/应用/患者端。"""
from __future__ import annotations

import json

import auth
import common
import db
import memory as memory_module
import templates as templates_mod

USERS = [
    ("u_admin", "王敏", "admin", "数据平台部", "#4F46E5"),
    ("u_creator", "张伟", "creator", "心血管内科", "#0EA5E9"),
    ("u_dept", "李主任", "dept_approver", "心血管内科", "#F59E0B"),
    ("u_platform", "孙悦", "platform_approver", "数据平台部", "#8B5CF6"),
    ("u_doctor", "王医生", "doctor", "心血管内科", "#10B981"),
    ("u_knowledge", "周婷", "knowledge_ops", "病案质控", "#EC4899"),
    ("u_eval", "陈静", "evaluator", "数据平台部", "#14B8A6"),
    ("u_patient", "赵磊", "patient", "患者", "#64748B"),
]
PASSWORD = "medagent123"

KNOWLEDGE = [
    {
        "title": "社区获得性肺炎诊疗指南（2026 版）",
        "source": "中华医学会呼吸病学分会",
        "owner": "心血管内科",
        "scope": ["公共", "心血管内科"],
        "content": "社区获得性肺炎（CAP）应评估病情严重程度，经验性抗感染治疗需覆盖常见病原体，"
                   "疗程一般 5-7 天，重症患者可延长；治疗 48-72 小时评估疗效，必要时调整方案。",
        "effective_at": "2026-01-01T00:00:00+08:00",
    },
    {
        "title": "院内输血知情同意制度",
        "source": "医务处",
        "owner": "医务处",
        "scope": ["公共"],
        "content": "输血前须完成输血知情同意书签署、输血前评估与相容性检测；紧急输血按院内应急预案执行，"
                   "并补记知情同意。知情同意书需患者或授权委托人签字。",
        "effective_at": "2026-01-01T00:00:00+08:00",
    },
    {
        "title": "华法林药品说明书（院内版）",
        "source": "药学部",
        "owner": "药学部",
        "scope": ["公共", "心血管内科"],
        "content": "华法林与多种药物存在相互作用，合用时应监测 INR；常见相互作用包括抗血小板药、"
                   "部分抗菌药、胺碘酮等。剂量调整须由医生根据 INR 与临床情况决定。",
        "effective_at": "2026-01-01T00:00:00+08:00",
    },
    {
        "title": "病历书写规范（院内 2026）",
        "source": "病案质控科",
        "owner": "病案质控科",
        "scope": ["公共", "病案质控"],
        "content": "入院记录应包含主诉、现病史、既往史、过敏史、体格检查、初步诊断等；"
                   "主诉应规范为“症状+时长”；病程记录按要求时限完成；手术记录与病程记录须一致。",
        "effective_at": "2026-01-01T00:00:00+08:00",
    },
    {
        "title": "2025 年医保支付政策（已过期）",
        "source": "医保办",
        "owner": "医保办",
        "scope": ["公共"],
        "content": "2025 年医保支付政策：住院起付线与报销比例按当年文件执行。本文件已于 2025-12-31 失效。",
        "effective_at": "2025-01-01T00:00:00+08:00",
        "expires_at": "2025-12-31T23:59:59+08:00",
        "status": "approved",
    },
    {
        "title": "2027 年新医保政策（待审核）",
        "source": "医保办",
        "owner": "医保办",
        "scope": ["公共"],
        "content": "2027 年医保支付政策调整草案，尚未审核，不得用于检索。",
        "effective_at": "2027-01-01T00:00:00+08:00",
        "status": "pending",
    },
]


def _insert_eval_dataset(conn, key, name, template_key, cases):
    dataset_id = conn.execute(
        "INSERT INTO eval_datasets(key, name, template_key, version, created_at) VALUES (?,?,?,?,?)",
        (key, name, template_key, 1, db.iso()),
    ).lastrowid
    for case in cases:
        conn.execute(
            "INSERT INTO eval_cases(dataset_id, input, expected, weight) VALUES (?,?,?,?)",
            (dataset_id, case[0], case[1], 1),
        )
    return dataset_id


def seed(conn) -> bool:
    if conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]:
        return False
    conn.execute("INSERT OR IGNORE INTO institutions(id, name) VALUES ('inst-001', '示范医院')")
    for user_id, name, role, department, color in USERS:
        conn.execute(
            "INSERT INTO users(id, name, role, department, password_hash, color) VALUES (?,?,?,?,?,?)",
            (user_id, name, role, department, auth.hash_password(PASSWORD), color),
        )
    # 模板
    for template in templates_mod.TEMPLATES.values():
        conn.execute(
            """INSERT INTO templates(key, name, version, risk_level, description, prompt_system,
                   prompt_user, output_schema, eval_threshold, config, status)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (template["key"], template["name"], template["version"], template["risk_level"],
             template["description"], template["prompt_system"], template["prompt_user"],
             json.dumps(template["output_schema"], ensure_ascii=False), template["eval_threshold"],
             json.dumps(template["config"], ensure_ascii=False), "approved"),
        )
    # 知识
    for doc in KNOWLEDGE:
        code = "K-" + str(conn.execute("SELECT COUNT(*) AS c FROM knowledge_docs").fetchone()["c"] + 1).zfill(4)
        conn.execute(
            """INSERT INTO knowledge_docs(code, title, source, owner, scope, version, effective_at,
                   expires_at, status, content, created_by, reviewed_by, reviewed_at, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (code, doc["title"], doc["source"], doc["owner"], json.dumps(doc["scope"], ensure_ascii=False),
             doc.get("version", 1), doc["effective_at"], doc.get("expires_at", ""),
             doc.get("status", "approved"), doc["content"], "u_knowledge", "u_knowledge",
             db.iso(), db.iso()),
        )
    # 模型与策略
    conn.executemany(
        "INSERT INTO models(key, name, provider, is_private, status, timeout_ms, description) VALUES (?,?,?,?,?,?,?)",
        [
            ("private-llm", "院内私有模型 7B", "openai_compatible", 1, "enabled", 30000, "院内私有化部署，数据不出院"),
            ("mock-fallback", "离线降级模型", "mock", 1, "enabled", 5000, "模型不可用时的降级路径，必须在界面标记"),
            ("cloud-fast", "云端快模型", "openai_compatible", 0, "disabled", 20000, "默认关闭，需出网审批后启用"),
        ],
    )
    conn.executemany(
        "INSERT INTO model_policies(key, name, chain, timeout_ms, retry, fallback_mode, status) VALUES (?,?,?,?,?,?,?)",
        [
            ("precise", "精准（私有优先）", json.dumps(["private-llm", "mock-fallback"]), 30000, 1, "degrade_marked", "enabled"),
            ("private", "私有（仅院内）", json.dumps(["private-llm", "mock-fallback"]), 30000, 1, "degrade_marked", "enabled"),
            ("fast", "快速（降级优先）", json.dumps(["mock-fallback"]), 10000, 1, "degrade_marked", "enabled"),
        ],
    )
    # 评测集
    knowledge_cases = [
        ("社区获得性肺炎抗感染治疗原则", "社区获得性肺炎,抗感染,疗程"),
        ("华法林与哪些药物相互作用", "华法林,相互作用,INR"),
        ("院内输血知情同意流程要求", "输血,知情同意,签字"),
        ("XX-999 新药的适应证与禁忌证", "未找到明确依据"),
        ("本院病历书写规范对主诉的要求", "主诉,规范"),
        ("一个不存在的 XX 疗法是否推荐", "未找到明确依据"),
    ]
    qc_cases = [
        ("患者主诉胸痛 3 天，现病史不详，诊断待查", "既往史,完整性"),
        ("入院记录：主诉胸痛，查体无异常，初步诊断待查", "过敏史,完整性"),
        ("病程记录仅一次，手术记录与病程不一致", "病程记录,一致性"),
        ("出院小结缺少医师签名", "签名,合法性"),
        ("主诉：胸痛，未注明时长", "主诉,完整性"),
    ]
    ds_knowledge = _insert_eval_dataset(conn, "ds-knowledge", "知识问答金标准集 v1", "med-knowledge", knowledge_cases)
    ds_qc = _insert_eval_dataset(conn, "ds-qc", "病历质控金标准集 v1", "med-qc", qc_cases)
    # 应用
    knowledge_config = dict(templates_mod.TEMPLATES["med-knowledge"]["config"])
    knowledge_config.update({"prompt_version": 1, "template_version": 1, "memory_enabled": True})
    qc_config = dict(templates_mod.TEMPLATES["med-qc"]["config"])
    qc_config.update({"prompt_version": 1, "template_version": 1, "memory_enabled": False})
    app_knowledge = conn.execute(
        """INSERT INTO apps(code, name, template_key, template_version, owner_id, department, status,
               risk_level, config, current_version, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        ("APP-0001", "临床知识问答（心内科）", "med-knowledge", 1, "u_creator", "心血管内科",
         "published", "low", json.dumps(knowledge_config, ensure_ascii=False), 1, db.iso(), db.iso()),
    ).lastrowid
    app_qc = conn.execute(
        """INSERT INTO apps(code, name, template_key, template_version, owner_id, department, status,
               risk_level, config, current_version, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        ("APP-0002", "病历质控试点", "med-qc", 1, "u_creator", "心血管内科",
         "draft", "medium", json.dumps(qc_config, ensure_ascii=False), 0, db.iso(), db.iso()),
    ).lastrowid
    snapshot = {
        "app_id": app_knowledge, "config": knowledge_config, "template_key": "med-knowledge",
        "template_version": 1, "prompt_version": 1, "model_policy": "precise",
        "knowledge_versions": [{"id": 1, "title": "社区获得性肺炎诊疗指南（2026 版）", "version": 1}],
        "eval_run_id": 1, "published_by": "u_platform", "published_at": db.iso(),
    }
    conn.execute(
        """INSERT INTO app_versions(app_id, version, snapshot, status, created_by, created_at, published_at)
           VALUES (?,?,?,?,?,?,?)""",
        (app_knowledge, 1, json.dumps(snapshot, ensure_ascii=False), "published", "u_platform", db.iso(), db.iso()),
    )
    conn.executemany(
        "INSERT INTO approvals(app_id, kind, status, reviewer_id, comment, created_at, decided_at) VALUES (?,?,?,?,?,?,?)",
        [
            (app_knowledge, "dept", "approved", "u_dept", "用途与内容审核通过", "2026-10-30T09:00:00+08:00", "2026-10-30T09:10:00+08:00"),
            (app_knowledge, "platform", "approved", "u_platform", "安全与技术条件通过", "2026-10-30T09:10:00+08:00", "2026-10-30T09:30:00+08:00"),
        ],
    )
    # 评测记录（种子：知识通过、质控未通过）
    run_knowledge = conn.execute(
        """INSERT INTO eval_runs(app_id, dataset_id, status, metrics, passed, threshold, gate_status, created_by, created_at)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (app_knowledge, ds_knowledge, "finished",
         json.dumps({"recall": 0.92, "citation_accuracy": 0.95, "answer_correct": 0.9,
                     "fabrication_rate": 0.0, "blocked_rate": 0.0}, ensure_ascii=False),
         1, 0.85, "passed", "u_eval", db.iso()),
    ).lastrowid
    run_qc = conn.execute(
        """INSERT INTO eval_runs(app_id, dataset_id, status, metrics, passed, threshold, gate_status, created_by, created_at)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (app_qc, ds_qc, "finished",
         json.dumps({"detection_rate": 0.52, "false_positive_rate": 0.1, "blocked_rate": 0.0}, ensure_ascii=False),
         0, 0.70, "failed", "u_eval", db.iso()),
    ).lastrowid
    for case_row in conn.execute("SELECT id FROM eval_cases WHERE dataset_id=?", (ds_knowledge,)).fetchall():
        conn.execute(
            "INSERT INTO eval_results(run_id, case_id, output, metrics, passed) VALUES (?,?,?,?,?)",
            (run_knowledge, case_row["id"], "根据院内已审核知识作答（种子样例）。",
             json.dumps({"score": 0.9, "citations": 1}), 1),
        )
    for case_row in conn.execute("SELECT id FROM eval_cases WHERE dataset_id=?", (ds_qc,)).fetchall():
        conn.execute(
            "INSERT INTO eval_results(run_id, case_id, output, metrics, passed) VALUES (?,?,?,?,?)",
            (run_qc, case_row["id"], "发现部分缺陷（种子样例）。",
             json.dumps({"score": 0.5, "citations": 0}), 0),
        )
    # BadCase / 安全事件 / 模型调用
    conn.executemany(
        "INSERT INTO badcases(app_id, source, question, output, category, severity, status, assignee, created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        [
            (app_knowledge, "u_doctor", "华法林与胺碘酮合用注意什么", "回答遗漏 INR 监测提示", "accuracy", "medium", "open", "", db.iso()),
            (app_qc, "u_eval", "病历缺过敏史未被提示", "缺陷清单漏检", "recall", "high", "assigned", "u_knowledge", db.iso()),
        ],
    )
    conn.execute(
        "INSERT INTO safety_events(app_id, run_id, category, severity, action, detail, created_at) VALUES (?,?,?,?,?,?,?)",
        (app_qc, None, "forbidden_output", "high", "blocked_and_handoff", "试跑输出命中“诊断”禁止项（种子）", db.iso()),
    )
    conn.executemany(
        "INSERT INTO model_calls(app_id, policy, model_key, degraded, latency_ms, tokens, cost, error_code, created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        [
            (app_knowledge, "precise", "private-llm", 0, 420, 180, 0.00036, "", db.iso()),
            (app_knowledge, "precise", "private-llm", 0, 380, 160, 0.00032, "", db.iso()),
            (app_qc, "precise", "mock-fallback", 1, 95, 120, 0.00024, "", db.iso()),
        ],
    )
    # 长期记忆（试跑注入演示）
    seed_memories = [
        ("agent", str(app_knowledge), "preference", "回答时先给结论，再列引用依据。", 3),
        ("user", "u_doctor", "fact", "关注心血管指南更新，尤其是抗感染疗程。", 2),
        ("tenant", "default", "instruction", "院内制度类问题优先引用医务处文件。", 3),
    ]
    for scope, owner, type_, content, importance in seed_memories:
        conn.execute(
            """INSERT INTO memories(scope, owner, type, content, importance, source, status, use_count,
                   content_hash, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (scope, owner, type_, content, importance, "seed", "active", 0,
             memory_module.content_hash(scope, owner, type_, content), db.iso(), db.iso()),
        )
    # 患者端
    conn.executemany(
        "INSERT INTO patients(patient_ref, name_mask, phone_mask, institution, created_at) VALUES (?,?,?,?,?)",
        [("P0001", "张*", "138****0001", "示范医院", db.iso()),
         ("P0002", "李*", "138****0002", "示范医院", db.iso())],
    )
    conn.executemany(
        "INSERT INTO reports(patient_ref, exam_type, reported_at, status, summary, approved_for_patient) VALUES (?,?,?,?,?,?)",
        [
            ("P0001", "胸部 CT", "2026-10-20T10:00:00+08:00", "已出具", "右肺上叶小结节，建议随访。", 1),
            ("P0001", "血常规", "2026-10-20T09:00:00+08:00", "已出具", "白细胞正常范围。", 0),
            ("P0002", "腹部超声", "2026-10-21T09:00:00+08:00", "已出具", "脂肪肝。", 1),
        ],
    )
    conn.executemany(
        "INSERT INTO followup_tasks(patient_ref, node, due_at, status, form, risk_flag, created_at) VALUES (?,?,?,?,?,?,?)",
        [
            ("P0001", "术后 7 天随访", "2026-10-31T18:00:00+08:00", "pending",
             json.dumps([{"key": "symptom", "label": "有无胸痛/呼吸困难/出血？", "type": "text"}] * 1, ensure_ascii=False), 0, db.iso()),
            ("P0001", "用药依从性随访", "2026-11-05T18:00:00+08:00", "pending",
             json.dumps([{"key": "med", "label": "是否按时服药？", "type": "text"}], ensure_ascii=False), 0, db.iso()),
        ],
    )
    # 审计
    conn.execute(
        "INSERT INTO audit_logs(actor, action, target_type, target_id, detail, created_at) "
        "VALUES (?,?,?,?,?,?)",
        ("system", "系统初始化", "system", "", "MediAgent v1.1 种子数据", db.iso()),
    )
    conn.commit()
    return True
