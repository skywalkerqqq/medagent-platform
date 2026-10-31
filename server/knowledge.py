"""知识中心：导入、审核、版本/生效/失效、权限与检索引用。"""
from __future__ import annotations

import re

import common
import db


def _grams(text: str) -> set[str]:
    text = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", str(text or "").lower())
    grams = set()
    for index in range(len(text) - 1):
        grams.add(text[index:index + 2])
    if not grams and text:
        grams.add(text)
    return grams


def _score(query: str, doc) -> float:
    content = (doc["title"] or "") + (doc["content"] or "")
    # 含英文/数字编号的查询（如 ZXQ-2026、XX-999）要求编号本身命中，避免“26”之类误召回
    tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]{2,}", query or "")
    if tokens:
        lowered = content.lower()
        if not any(token.lower() in lowered for token in tokens):
            return 0.0
    q = _grams(query)
    if not q:
        return 0.0
    c = _grams(content)
    return len(q & c) / len(q)


def _active_clause() -> tuple[str, list]:
    now = db.iso()
    return (
        "status='approved' AND (effective_at IS NULL OR effective_at <= ?) "
        "AND (expires_at IS NULL OR expires_at = '' OR expires_at > ?)",
        [now, now],
    )


def search(conn, query: str, scope: list[str] | None = None, limit: int = 5) -> list[dict]:
    clause, params = _active_clause()
    sql = f"SELECT * FROM knowledge_docs WHERE {clause}"
    docs = conn.execute(sql, params).fetchall()
    hits = []
    for doc in docs:
        if scope:
            doc_scope = common.loads(doc["scope"], []) or []
            if not (set(scope) & set(doc_scope)) and "公共" not in doc_scope:
                continue
        score = _score(query, doc)
        if score < 0.25:  # 低分噪声（如仅“26”命中）不得作为依据
            continue
        excerpt = (doc["content"] or "")[:180]
        hits.append({
            "doc_id": doc["id"],
            "title": doc["title"],
            "source": doc["source"],
            "version": doc["version"],
            "effective_at": doc["effective_at"],
            "excerpt": excerpt,
            "score": round(score, 3),
            "citation": f"[{doc['title']}·v{doc['version']}]",
        })
    hits.sort(key=lambda item: (-item["score"], item["doc_id"]))
    return hits[: max(1, min(int(limit or 5), 20))]


def scope_has_docs(conn, scope: list[str]) -> bool:
    """范围内是否存在已审核且生效的知识（不依赖查询词）。"""
    clause, params = _active_clause()
    rows = conn.execute(f"SELECT scope FROM knowledge_docs WHERE {clause}", params).fetchall()
    scopes = set(scope or [])
    for row in rows:
        doc_scope = common.loads(row["scope"], []) or []
        if "公共" in doc_scope or (scopes & set(doc_scope)):
            return True
    return False


def list_docs(ctx):
    common.require(ctx["user"], "knowledge:read")
    query = ctx["query"]
    where, params = [], []
    if query.get("status"):
        where.append("status=?")
        params.append(query["status"])
    if query.get("scope"):
        where.append("scope LIKE ?")
        params.append(f"%{query['scope']}%")
    if query.get("q"):
        where.append("(title LIKE ? OR content LIKE ? OR source LIKE ?)")
        keyword = f"%{query['q']}%"
        params.extend([keyword, keyword, keyword])
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    limit, offset = common.pagination(query)
    total = ctx["conn"].execute(f"SELECT COUNT(*) AS c FROM knowledge_docs{clause}", params).fetchone()["c"]
    rows = ctx["conn"].execute(
        f"SELECT * FROM knowledge_docs{clause} ORDER BY id DESC LIMIT ? OFFSET ?", params + [limit, offset]
    ).fetchall()
    items = []
    for row in rows:
        item = dict(row)
        item["scope"] = common.loads(item["scope"], []) or []
        items.append(item)
    return 200, {"items": items, "total": total}


def import_doc(ctx):
    conn, user, body = ctx["conn"], ctx["user"], ctx["body"]
    common.require(user, "knowledge:write", "仅知识运营/管理员可导入知识")
    title = common.str_field(body.get("title"), "title", required=True)
    source = common.str_field(body.get("source"), "source", required=True)
    owner = common.str_field(body.get("owner"), "owner", required=True)
    content = common.str_field(body.get("content"), "content", required=True)
    scope = body.get("scope") or ["公共"]
    if not isinstance(scope, list) or not scope:
        raise common.ApiError(400, "validation", "scope 必须是非空数组")
    effective_at = common.str_field(body.get("effective_at"), "effective_at", required=True)
    expires_at = common.str_field(body.get("expires_at"), "expires_at", default="")
    version = common.int_field(body.get("version"), "version", default=1, minimum=1)
    code = "K-" + str(conn.execute("SELECT COUNT(*) AS c FROM knowledge_docs").fetchone()["c"] + 1).zfill(4)
    doc_id = conn.execute(
        """INSERT INTO knowledge_docs(code, title, source, owner, scope, version, effective_at, expires_at,
               status, content, created_by, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (code, title, source, owner, common.dumps(scope), version, effective_at, expires_at,
         "pending", content, user["id"], db.iso()),
    ).lastrowid
    common.audit(conn, user["id"], "导入知识", "knowledge", doc_id, f"《{title}》来源：{source}")
    conn.commit()
    return 201, {"id": doc_id, "code": code, "status": "pending", "note": "待知识运营审核后生效"}


def review_doc(ctx):
    conn, user, body = ctx["conn"], ctx["user"], ctx["body"]
    common.require(user, "knowledge:review", "仅知识审核/管理员可审核知识")
    doc_id = int(ctx["params"]["id"])
    doc = conn.execute("SELECT * FROM knowledge_docs WHERE id=?", (doc_id,)).fetchone()
    if not doc:
        raise common.ApiError(404, "not_found", "知识不存在")
    decision = common.str_field(body.get("decision"), "decision", required=True)
    if decision not in ("approve", "reject"):
        raise common.ApiError(400, "validation", "decision 只能是 approve/reject")
    status = "approved" if decision == "approve" else "rejected"
    comment = common.str_field(body.get("comment"), "comment", default="")
    conn.execute(
        "UPDATE knowledge_docs SET status=?, reviewed_by=?, reviewed_at=?, review_comment=? WHERE id=?",
        (status, user["id"], db.iso(), comment, doc_id),
    )
    common.audit(conn, user["id"], "审核知识", "knowledge", doc_id, f"{decision} {comment}".strip())
    conn.commit()
    return 200, {"id": doc_id, "status": status}


def search_handler(ctx):
    common.require(ctx["user"], "knowledge:read")
    query = ctx["query"]
    q = common.str_field(query.get("q"), "q", required=True)
    scope = [s for s in (query.get("scope") or "").split(",") if s]
    hits = search(ctx["conn"], q, scope or None, int(query.get("top", 5)))
    return 200, {"query": q, "hits": hits, "total": len(hits)}


def detail(ctx):
    common.require(ctx["user"], "knowledge:read")
    doc = ctx["conn"].execute(
        "SELECT * FROM knowledge_docs WHERE id=?", (int(ctx["params"]["id"]),)
    ).fetchone()
    if not doc:
        raise common.ApiError(404, "not_found", "知识不存在")
    data = dict(doc)
    data["scope"] = common.loads(data["scope"], []) or []
    return 200, data


ROUTES = [
    ("GET", re.compile(r"^/api/knowledge$"), list_docs),
    ("POST", re.compile(r"^/api/knowledge$"), import_doc),
    ("GET", re.compile(r"^/api/knowledge/search$"), search_handler),
    ("GET", re.compile(r"^/api/knowledge/(?P<id>\d+)$"), detail),
    ("POST", re.compile(r"^/api/knowledge/(?P<id>\d+)/review$"), review_doc),
]
