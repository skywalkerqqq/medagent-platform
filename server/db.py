"""SQLite 存储层：MediAgent 中台 v1.1。"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS institutions (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    role TEXT NOT NULL,
    department TEXT,
    password_hash TEXT,
    color TEXT
);

CREATE TABLE IF NOT EXISTS auth_sessions (
    token TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    created_at TEXT,
    expires_at TEXT
);

CREATE TABLE IF NOT EXISTS templates (
    key TEXT PRIMARY KEY,
    name TEXT,
    version INTEGER,
    risk_level TEXT,
    description TEXT,
    prompt_system TEXT,
    prompt_user TEXT,
    output_schema TEXT,
    eval_threshold REAL,
    config TEXT,
    status TEXT
);

CREATE TABLE IF NOT EXISTS knowledge_docs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE,
    title TEXT,
    source TEXT,
    owner TEXT,
    scope TEXT,
    version INTEGER DEFAULT 1,
    effective_at TEXT,
    expires_at TEXT,
    status TEXT DEFAULT 'pending',
    content TEXT,
    created_by TEXT,
    reviewed_by TEXT,
    reviewed_at TEXT,
    review_comment TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS report_drafts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE,
    app_id INTEGER,
    patient_ref TEXT,
    exam_type TEXT,
    findings_original TEXT,
    findings TEXT,
    impression_original TEXT,
    impression TEXT,
    recommendation_original TEXT,
    recommendation TEXT,
    missing_fields TEXT,                -- JSON array
    status TEXT DEFAULT 'draft',        -- draft | signed
    editor_id TEXT,
    edit_rate REAL,
    created_by TEXT,
    created_at TEXT,
    updated_at TEXT,
    signed_at TEXT,
    external_id TEXT,
    written_back_at TEXT
);

CREATE TABLE IF NOT EXISTS integration_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    integration TEXT,
    action TEXT,
    target TEXT,
    status TEXT,
    external_id TEXT,
    detail TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS faqs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    scope TEXT,                         -- JSON array
    source TEXT,
    status TEXT DEFAULT 'pending',      -- pending | approved | rejected
    created_by TEXT,
    reviewed_by TEXT,
    reviewed_at TEXT,
    review_comment TEXT,
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS apps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE,
    name TEXT NOT NULL,
    template_key TEXT NOT NULL,
    template_version INTEGER DEFAULT 1,
    owner_id TEXT,
    department TEXT,
    status TEXT DEFAULT 'draft',
    risk_level TEXT,
    config TEXT,
    current_version INTEGER DEFAULT 0,
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS app_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    app_id INTEGER NOT NULL,
    version INTEGER NOT NULL,
    snapshot TEXT,
    status TEXT,
    created_by TEXT,
    created_at TEXT,
    published_at TEXT
);

CREATE TABLE IF NOT EXISTS approvals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    app_id INTEGER NOT NULL,
    kind TEXT,
    status TEXT DEFAULT 'pending',
    reviewer_id TEXT,
    comment TEXT,
    created_at TEXT,
    decided_at TEXT
);

CREATE TABLE IF NOT EXISTS eval_datasets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT UNIQUE,
    name TEXT,
    template_key TEXT,
    version INTEGER,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS eval_cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_id INTEGER NOT NULL,
    input TEXT,
    expected TEXT,
    weight REAL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS eval_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    app_id INTEGER,
    dataset_id INTEGER,
    status TEXT,
    metrics TEXT,
    passed INTEGER DEFAULT 0,
    threshold REAL,
    gate_status TEXT,
    created_by TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS eval_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER,
    case_id INTEGER,
    output TEXT,
    metrics TEXT,
    passed INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS badcases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    app_id INTEGER,
    source TEXT,
    question TEXT,
    output TEXT,
    category TEXT,
    severity TEXT DEFAULT 'medium',
    status TEXT DEFAULT 'open',
    assignee TEXT,
    resolution TEXT,
    created_at TEXT,
    closed_at TEXT
);

CREATE TABLE IF NOT EXISTS safety_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    app_id INTEGER,
    run_id INTEGER,
    category TEXT,
    severity TEXT,
    action TEXT,
    detail TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor TEXT,
    action TEXT,
    target_type TEXT,
    target_id TEXT,
    detail TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS models (
    key TEXT PRIMARY KEY,
    name TEXT,
    provider TEXT,
    is_private INTEGER DEFAULT 1,
    status TEXT DEFAULT 'enabled',
    timeout_ms INTEGER DEFAULT 30000,
    description TEXT
);

CREATE TABLE IF NOT EXISTS model_policies (
    key TEXT PRIMARY KEY,
    name TEXT,
    chain TEXT,
    timeout_ms INTEGER DEFAULT 30000,
    retry INTEGER DEFAULT 1,
    fallback_mode TEXT DEFAULT 'degrade_marked',
    status TEXT DEFAULT 'enabled'
);

CREATE TABLE IF NOT EXISTS model_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    app_id INTEGER,
    policy TEXT,
    model_key TEXT,
    degraded INTEGER DEFAULT 0,
    latency_ms INTEGER,
    tokens INTEGER,
    cost REAL,
    error_code TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS patients (
    patient_ref TEXT PRIMARY KEY,
    name_mask TEXT,
    phone_mask TEXT,
    institution TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS patient_bindings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    patient_ref TEXT,
    consent TEXT,
    status TEXT DEFAULT 'active',
    bound_at TEXT,
    revoked_at TEXT
);

CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_ref TEXT,
    exam_type TEXT,
    reported_at TEXT,
    status TEXT,
    summary TEXT,
    approved_for_patient INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS followup_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_ref TEXT,
    node TEXT,
    due_at TEXT,
    status TEXT DEFAULT 'pending',
    form TEXT,
    answers TEXT,
    risk_flag INTEGER DEFAULT 0,
    created_at TEXT,
    submitted_at TEXT
);

CREATE TABLE IF NOT EXISTS handoffs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_ref TEXT,
    task_id INTEGER,
    reason TEXT,
    status TEXT DEFAULT 'pending',
    assigned_to TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scope TEXT,                         -- user | agent | tenant
    owner TEXT,                         -- user_id / app_id / default
    type TEXT,                          -- preference | fact | summary | instruction
    content TEXT,
    importance INTEGER DEFAULT 2,
    source TEXT DEFAULT 'manual',
    status TEXT DEFAULT 'active',       -- active | deleted
    use_count INTEGER DEFAULT 0,
    content_hash TEXT,
    embedding TEXT,                     -- 64 维 bigram 向量（JSON）
    created_at TEXT,
    updated_at TEXT,
    last_used_at TEXT,
    expires_at TEXT
);

CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    app_id INTEGER,
    user_id TEXT,
    status TEXT DEFAULT 'open',         -- open | closed
    summary_memory_id INTEGER,
    created_at TEXT,
    closed_at TEXT
);

CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    app_id INTEGER,
    session_id INTEGER,
    user_id TEXT,
    input TEXT,
    output TEXT,
    summary_text TEXT,                  -- 记忆摘要用的干净回答（不含注入前缀）
    status TEXT DEFAULT 'succeeded',
    degraded INTEGER DEFAULT 0,
    tokens INTEGER DEFAULT 0,
    cost REAL DEFAULT 0,
    latency_ms INTEGER DEFAULT 0,
    memory_written INTEGER DEFAULT 0,
    created_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_sessions_user ON auth_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_apps_status ON apps(status);
CREATE INDEX IF NOT EXISTS idx_versions_app ON app_versions(app_id, version);
CREATE INDEX IF NOT EXISTS idx_approvals_app ON approvals(app_id, kind, status);
CREATE INDEX IF NOT EXISTS idx_eval_cases_ds ON eval_cases(dataset_id);
CREATE INDEX IF NOT EXISTS idx_eval_results_run ON eval_results(run_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_status ON knowledge_docs(status);
CREATE INDEX IF NOT EXISTS idx_faqs_status ON faqs(status);
CREATE INDEX IF NOT EXISTS idx_reports_status ON report_drafts(status);
CREATE INDEX IF NOT EXISTS idx_integration_calls ON integration_calls(integration, created_at);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_calls_app ON model_calls(app_id, created_at);
CREATE INDEX IF NOT EXISTS idx_bindings_user ON patient_bindings(user_id, status);
CREATE INDEX IF NOT EXISTS idx_reports_patient ON reports(patient_ref);
CREATE INDEX IF NOT EXISTS idx_followups_patient ON followup_tasks(patient_ref, status);
CREATE INDEX IF NOT EXISTS idx_memories_scope ON memories(scope, owner, status);
CREATE INDEX IF NOT EXISTS idx_memories_hash ON memories(content_hash);
CREATE INDEX IF NOT EXISTS idx_sessions_app ON sessions(app_id, user_id, status);
CREATE INDEX IF NOT EXISTS idx_runs_app ON runs(app_id, created_at);
CREATE INDEX IF NOT EXISTS idx_runs_session ON runs(session_id);
"""


def now() -> datetime:
    return datetime.now().astimezone()


def iso(value: datetime | None = None) -> str:
    return (value or now()).isoformat(timespec="seconds")


def future(hours: int) -> str:
    return iso(now() + timedelta(hours=hours))


def connect(path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def init_db(path, reset: bool = False) -> sqlite3.Connection:
    path = Path(path)
    if reset:
        for suffix in ("", "-wal", "-shm"):
            Path(str(path) + suffix).unlink(missing_ok=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(path)
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    try:
        conn.execute("PRAGMA journal_mode = WAL")
    except sqlite3.Error:
        pass
    conn.close()
    return connect(path)
