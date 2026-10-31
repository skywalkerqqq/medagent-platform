"""HIS / EMR / PACS 集成（POC mock）。

- `/api/integrations/status`：如实显示 mock 模式（未接真实院内接口）；
- `/api/integrations/patient/{patient_ref}`：聚合患者主数据、就诊、影像检查（模拟 HIS/EMR/PACS）；
- `/api/integrations/report-writeback`：签名报告回写 HIS（mock，幂等，记录外部 ID 与审计）；
- `/api/integrations/calls`：集成调用记录。
"""
from __future__ import annotations

import re
import secrets

import common
import db

MOCK_PATIENTS = {
    "P0001": {
        "patient_ref": "P0001",
        "name_mask": "张*",
        "sex": "女",
        "age": 52,
        "allergies": ["青霉素"],
        "encounters": [
            {"encounter_id": "ENC-20261020-01", "date": "2026-10-20", "department": "心血管内科",
             "doctor": "王医生", "diagnosis": "高血压 2 级（待复核）", "status": "已就诊"},
            {"encounter_id": "ENC-20260901-02", "date": "2026-09-01", "department": "心血管内科",
             "doctor": "李主任", "diagnosis": "胸闷待查", "status": "已就诊"},
        ],
        "studies": [
            {"study_id": "ST-20261020-CT-01", "date": "2026-10-20", "modality": "CT",
             "body_part": "胸部", "report_status": "报告已出具", "accession": "ACC-1001"},
            {"study_id": "ST-20260901-US-02", "date": "2026-09-01", "modality": "US",
             "body_part": "腹部", "report_status": "报告已出具", "accession": "ACC-1002"},
        ],
    },
    "P0002": {
        "patient_ref": "P0002",
        "name_mask": "李*",
        "sex": "男",
        "age": 61,
        "allergies": ["造影剂"],
        "encounters": [
            {"encounter_id": "ENC-20261021-01", "date": "2026-10-21", "department": "心血管内科",
             "doctor": "王医生", "diagnosis": "脂肪肝（待复核）", "status": "已就诊"},
        ],
        "studies": [
            {"study_id": "ST-20261021-US-01", "date": "2026-10-21", "modality": "US",
             "body_part": "腹部", "report_status": "报告已出具", "accession": "ACC-2001"},
        ],
    },
}


def status(ctx):
    return 200, {
        "mode": "mock",
        "items": [
            {"name": "his", "configured": True, "mode": "mock",
             "detail": "患者主数据/就诊（mock；真实接口待院方提供）"},
            {"name": "emr", "configured": True, "mode": "mock",
             "detail": "电子病历/诊断（mock；真实接口待院方提供）"},
            {"name": "pacs", "configured": True, "mode": "mock",
             "detail": "DICOMweb/影像检查（mock；真实 PACS 待联调）"},
        ],
        "note": "POC 使用合成数据；本接口不返回姓名/证件/手机号等直接标识。",
    }


def patient_context(ctx):
    common.require(ctx["user"], "report:read")
    patient_ref = common.str_field(ctx["params"]["patient_ref"], "patient_ref", required=True)
    data = MOCK_PATIENTS.get(patient_ref.upper())
    if not data:
        raise common.ApiError(404, "not_found", "患者不存在或未授权（POC 演示：P0001/P0002）")
    payload = dict(data)
    payload.update({
        "sources": ["mock-his", "mock-emr", "mock-pacs"],
        "fetched_at": db.iso(),
        "note": "合成脱敏数据；真实字段映射与授权须由院方确认",
    })
    return 200, payload


def writeback(ctx):
    conn, user, body = ctx["conn"], ctx["user"], ctx["body"]
    common.require(user, "report:write", "无报告回写权限")
    report_id = common.int_field(body.get("report_id"), "report_id", minimum=1)
    row = conn.execute("SELECT * FROM report_drafts WHERE id=?", (report_id,)).fetchone()
    if not row:
        raise common.ApiError(404, "not_found", "报告不存在")
    if row["status"] != "signed":
        raise common.ApiError(409, "conflict", "仅已签名报告可回写 HIS")
    if row["written_back_at"]:
        return 200, {"ok": True, "idempotent": True, "report_id": report_id,
                     "external_id": row["external_id"], "written_back_at": row["written_back_at"],
                     "note": "已回写，重复请求不重复写入"}
    external_id = "HIS-RPT-" + str(report_id).zfill(4) + "-" + secrets.token_hex(3).upper()
    now = db.iso()
    conn.execute("UPDATE report_drafts SET external_id=?, written_back_at=?, updated_at=? WHERE id=?",
                 (external_id, now, now, report_id))
    conn.execute(
        "INSERT INTO integration_calls(integration, action, target, status, external_id, detail, created_at) "
        "VALUES (?,?,?,?,?,?,?)",
        ("his", "report_writeback", f"report:#{report_id}", "succeeded", external_id,
         f"回写报告 {row['code']}（mock）", now),
    )
    common.audit(conn, user["id"], "回写 HIS", "report", report_id, f"external_id={external_id}")
    conn.commit()
    return 200, {"ok": True, "idempotent": False, "report_id": report_id,
                 "external_id": external_id, "written_back_at": now,
                 "note": "mock HIS 回写成功；真实 HIS 须院方接口联调与授权"}


def calls(ctx):
    common.require(ctx["user"], "report:read")
    rows = ctx["conn"].execute(
        "SELECT * FROM integration_calls ORDER BY id DESC LIMIT 50").fetchall()
    return 200, {"items": [dict(row) for row in rows]}


ROUTES = [
    ("GET", re.compile(r"^/api/integrations/status$"), status),
    ("GET", re.compile(r"^/api/integrations/patient/(?P<patient_ref>[A-Za-z0-9_-]+)$"), patient_context),
    ("POST", re.compile(r"^/api/integrations/report-writeback$"), writeback),
    ("GET", re.compile(r"^/api/integrations/calls$"), calls),
]
