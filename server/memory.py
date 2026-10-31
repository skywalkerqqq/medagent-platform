"""长期记忆：三级范围（user/agent/tenant）× 四类（偏好/事实/摘要/指令）。

- 试跑时若应用开启 memory_enabled，注入相关记忆并写入执行轨迹；
- 去重（scope/owner/type/content 哈希）、软删/硬删、过期治理、使用计数。
"""
from __future__ import annotations

import hashlib
import json
import math
import re

import common
import db

SCOPES = ("user", "agent", "tenant")
TYPES = ("preference", "fact", "summary", "instruction")
EMBED_DIM = 64
DISCLAIMER = "本结果为 AI 辅助信息，不构成诊疗建议；须由具备资质的医生复核确认。"


def content_hash(scope: str, owner: str, type_: str, content: str) -> str:
    raw = f"{scope}|{owner}|{type_}|{content.strip()}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _grams(text: str) -> list[str]:
    text = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", str(text or "").lower())
    grams = [text[index:index + 2] for index in range(len(text) - 1)]
    return grams or ([text] if text else [])


def embedding_for(text: str) -> list[float]:
    """64 维 bigram 哈希向量（L2 归一化），与旧版 AgentHub 的轻量向量检索一致。"""
    vector = [0.0] * EMBED_DIM
    for gram in _grams(text):
        digest = hashlib.md5(gram.encode("utf-8")).hexdigest()
        index = int(digest[:8], 16) % EMBED_DIM
        vector[index] += 1.0
    norm = math.sqrt(sum(value * value for value in vector))
    if norm:
        vector = [round(value / norm, 6) for value in vector]
    return vector


def embedding_json(text: str) -> str:
    return json.dumps(embedding_for(text), ensure_ascii=False)


def _parse_embedding(raw) -> list[float]:
    if not raw:
        return []
    try:
        values = json.loads(raw)
        return [float(value) for value in values] if isinstance(values, list) else []
    except (ValueError, TypeError):
        return []


def _cosine(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    return sum(a * b for a, b in zip(left, right))


def _keyword_score(query: str, content: str) -> float:
    q = set(_grams(query))
    if not q:
        return 0.0
    return len(q & set(_grams(content))) / len(q)


def _json(row) -> dict:
    data = dict(row)
    data["has_embedding"] = bool(data.get("embedding"))
    data.pop("embedding", None)
    return data


def _owner_default(user, scope, owner):
    owner = str(owner or "").strip()
    if owner:
        return owner
    if scope == "user":
        return user["id"]
    if scope == "tenant":
        return "default"
    raise common.ApiError(400, "validation", "agent 范围必须提供 owner（应用 ID）")


def list_memories(ctx):
    common.require(ctx["user"], "memory:read")
    query = ctx["query"]
    mode = (query.get("mode") or "vector").lower()
    where, params = [], []
    if query.get("scope"):
        where.append("scope=?")
        params.append(query["scope"])
    if query.get("type"):
        where.append("type=?")
        params.append(query["type"])
    if query.get("status"):
        where.append("status=?")
        params.append(query["status"])
    if query.get("q"):
        where.append("content LIKE ?")
        params.append(f"%{query['q']}%")
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    limit, offset = common.pagination(query)
    total = ctx["conn"].execute(f"SELECT COUNT(*) AS c FROM memories{clause}", params).fetchone()["c"]
    rows = ctx["conn"].execute(
        f"SELECT * FROM memories{clause} ORDER BY importance DESC, id DESC LIMIT ? OFFSET ?",
        params + [limit, offset],
    ).fetchall()
    stats = {
        "total": ctx["conn"].execute("SELECT COUNT(*) FROM memories").fetchone()[0],
        "active": ctx["conn"].execute("SELECT COUNT(*) FROM memories WHERE status='active'").fetchone()[0],
        "by_type": {row["type"]: row["c"] for row in ctx["conn"].execute(
            "SELECT type, COUNT(*) AS c FROM memories WHERE status='active' GROUP BY type").fetchall()},
        "total_use": ctx["conn"].execute("SELECT COALESCE(SUM(use_count),0) FROM memories").fetchone()[0],
        "with_embedding": ctx["conn"].execute(
            "SELECT COUNT(*) FROM memories WHERE embedding IS NOT NULL AND embedding != ''").fetchone()[0],
    }
    return 200, {"items": [_json(row) for row in rows], "total": total, "stats": stats,
                 "scopes": list(SCOPES), "types": list(TYPES), "search_mode": mode,
                 "embedding_dim": EMBED_DIM}


def search_memories(ctx):
    common.require(ctx["user"], "memory:read")
    query = common.str_field(ctx["query"].get("q"), "q", required=True)
    mode = (ctx["query"].get("mode") or "vector").lower()
    limit = common.int_field(ctx["query"].get("limit"), "limit", default=5, minimum=1, maximum=20)
    rows = ctx["conn"].execute(
        "SELECT * FROM memories WHERE status='active' "
        "AND (expires_at IS NULL OR expires_at='' OR expires_at > ?)", (db.iso(),)).fetchall()
    query_vector = embedding_for(query) if mode == "vector" else []
    scored = []
    for row in rows:
        keyword = _keyword_score(query, row["content"])
        if mode == "vector":
            score = 0.8 * _cosine(query_vector, _parse_embedding(row["embedding"])) + 0.2 * keyword
        else:
            score = keyword
        if score > 0.02:
            scored.append((round(score, 4), row))
    scored.sort(key=lambda item: -item[0])
    items = []
    for score, row in scored[:limit]:
        data = _json(row)
        data["score"] = score
        items.append(data)
    return 200, {"query": query, "mode": mode, "items": items, "total": len(items)}


def create_memory(ctx):
    conn, user, body = ctx["conn"], ctx["user"], ctx["body"]
    common.require(user, "memory:write", "无记忆写入权限")
    scope = common.str_field(body.get("scope"), "scope", required=True)
    if scope not in SCOPES:
        raise common.ApiError(400, "validation", "scope 只能是 user/agent/tenant")
    type_ = common.str_field(body.get("type"), "type", required=True)
    if type_ not in TYPES:
        raise common.ApiError(400, "validation", "type 只能是 preference/fact/summary/instruction")
    content = common.str_field(body.get("content"), "content", required=True)
    owner = _owner_default(user, scope, body.get("owner"))
    if scope == "agent":
        if not owner.isdigit() or not conn.execute("SELECT 1 FROM apps WHERE id=?", (int(owner),)).fetchone():
            raise common.ApiError(400, "validation", "agent 范围 owner 必须是存在的应用 ID")
    importance = common.int_field(body.get("importance"), "importance", default=2, minimum=1, maximum=3)
    expires_at = common.str_field(body.get("expires_at"), "expires_at", default="")
    digest = content_hash(scope, owner, type_, content)
    embedding = embedding_json(content)
    existing = conn.execute(
        "SELECT * FROM memories WHERE scope=? AND owner=? AND type=? AND content_hash=?",
        (scope, owner, type_, digest),
    ).fetchone()
    if existing:
        conn.execute("UPDATE memories SET importance=?, expires_at=?, embedding=?, updated_at=? WHERE id=?",
                     (importance, expires_at, embedding, db.iso(), existing["id"]))
        common.audit(conn, user["id"], "记忆去重", "memory", existing["id"], "重复内容已合并")
        conn.commit()
        return 200, {"id": existing["id"], "deduped": True, "status": existing["status"],
                     "note": "相同 scope/owner/type/content 已存在，已更新重要度"}
    memory_id = conn.execute(
        """INSERT INTO memories(scope, owner, type, content, importance, source, status, use_count,
               content_hash, embedding, created_at, updated_at, expires_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (scope, owner, type_, content, importance, "manual", "active", 0, digest, embedding,
         db.iso(), db.iso(), expires_at),
    ).lastrowid
    common.audit(conn, user["id"], "创建记忆", "memory", memory_id, f"{scope}/{type_}")
    conn.commit()
    row = conn.execute("SELECT * FROM memories WHERE id=?", (memory_id,)).fetchone()
    return 201, {**_json(row), "deduped": False}


def update_memory(ctx):
    conn, user, body = ctx["conn"], ctx["user"], ctx["body"]
    common.require(user, "memory:write")
    memory_id = int(ctx["params"]["id"])
    row = conn.execute("SELECT * FROM memories WHERE id=?", (memory_id,)).fetchone()
    if not row:
        raise common.ApiError(404, "not_found", "记忆不存在")
    if user["role"] != "admin" and row["scope"] == "user" and row["owner"] != user["id"]:
        raise common.ApiError(403, "forbidden", "只能修改自己的用户记忆")
    if user["role"] != "admin" and row["scope"] != "user":
        raise common.ApiError(403, "forbidden", "仅管理员可修改 agent/tenant 记忆")
    content = common.str_field(body.get("content"), "content", default=row["content"])
    importance = common.int_field(body.get("importance"), "importance", default=row["importance"],
                                  minimum=1, maximum=3)
    expires_at = common.str_field(body.get("expires_at"), "expires_at", default=row["expires_at"] or "")
    status = common.str_field(body.get("status"), "status", default=row["status"])
    if status not in ("active", "deleted"):
        raise common.ApiError(400, "validation", "status 只能是 active/deleted")
    digest = content_hash(row["scope"], row["owner"], row["type"], content)
    conn.execute(
        "UPDATE memories SET content=?, importance=?, expires_at=?, status=?, content_hash=?, embedding=?, updated_at=? WHERE id=?",
        (content, importance, expires_at, status, digest, embedding_json(content), db.iso(), memory_id),
    )
    common.audit(conn, user["id"], "更新记忆", "memory", memory_id, status)
    conn.commit()
    return 200, _json(conn.execute("SELECT * FROM memories WHERE id=?", (memory_id,)).fetchone())


def delete_memory(ctx):
    conn, user = ctx["conn"], ctx["user"]
    common.require(user, "memory:write")
    memory_id = int(ctx["params"]["id"])
    row = conn.execute("SELECT * FROM memories WHERE id=?", (memory_id,)).fetchone()
    if not row:
        raise common.ApiError(404, "not_found", "记忆不存在")
    if user["role"] != "admin" and row["scope"] == "user" and row["owner"] != user["id"]:
        raise common.ApiError(403, "forbidden", "只能删除自己的用户记忆")
    if user["role"] != "admin" and row["scope"] != "user":
        raise common.ApiError(403, "forbidden", "仅管理员可删除 agent/tenant 记忆")
    hard = (ctx["query"].get("hard") or "").lower() in ("1", "true", "yes")
    if hard:
        common.require(user, "admin", "硬删除仅管理员可执行")
        conn.execute("DELETE FROM memories WHERE id=?", (memory_id,))
        action = "硬删除记忆"
    else:
        conn.execute("UPDATE memories SET status='deleted', updated_at=? WHERE id=?", (db.iso(), memory_id))
        action = "删除记忆（软删）"
    common.audit(conn, user["id"], action, "memory", memory_id, "")
    conn.commit()
    return 200, {"ok": True, "hard": hard}


# ---------------------------------------------------------------- 运行时检索
def _grams(text: str) -> set[str]:
    text = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", str(text or "").lower())
    return {text[index:index + 2] for index in range(len(text) - 1)} or ({text} if text else set())


def retrieve(conn, app_id, user_id, query: str, limit: int = 3, mode: str = "vector") -> list[dict]:
    """按 user/agent/tenant 范围检索相关记忆（仅 active 且未过期）。

    mode=vector：64 维 bigram 余弦相似度 + 关键词加权；mode=bigram：仅关键词。
    """
    rows = conn.execute(
        """SELECT * FROM memories WHERE status='active'
           AND (expires_at IS NULL OR expires_at='' OR expires_at > ?)
           AND ((scope='user' AND owner=?) OR (scope='agent' AND owner=?) OR (scope='tenant' AND owner='default'))""",
        (db.iso(), str(user_id or ""), str(app_id)),
    ).fetchall()
    query_vector = embedding_for(query) if mode == "vector" else []
    scored = []
    for row in rows:
        keyword = _keyword_score(query, row["content"])
        if mode == "vector":
            vector_score = _cosine(query_vector, _parse_embedding(row["embedding"]))
            score = 0.8 * vector_score + 0.2 * keyword
        else:
            score = keyword
        if score <= 0.02 and keyword <= 0.02:
            continue
        scored.append((score + 0.1 * int(row["importance"] or 1), row))
    scored.sort(key=lambda item: -item[0])
    return [dict(row) for _, row in scored[:limit]]


def write_summary(conn, app_id, user_id, runs, source: str, mode: str) -> int | None:
    """把运行/会话摘要写入记忆（去重），返回 memory_id。source=run|session。"""
    runs = [dict(run) for run in runs if run]
    if not runs:
        return None
    if source == "session":
        inputs = [str(run.get("input") or "")[:40] for run in runs[-3:]]
        content = (f"会话摘要（{len(runs)}轮）：用户询问" + "；".join(f"「{item}」" for item in inputs)
                   + f"。最近一次建议：{str(runs[-1].get('summary_text') or runs[-1].get('output') or '')[:120]}")
        scope, owner = "user", str(user_id or "")
    else:
        run = runs[-1]
        content = (f"运行摘要：用户询问「{str(run.get('input') or '')[:60]}」；"
                   f"系统建议「{str(run.get('summary_text') or run.get('output') or '')[:140]}」")
        scope, owner = "agent", str(app_id)
    digest = content_hash(scope, owner, "summary", content)
    existing = conn.execute(
        "SELECT * FROM memories WHERE scope=? AND owner=? AND type='summary' AND content_hash=?",
        (scope, owner, digest),
    ).fetchone()
    if existing:
        return existing["id"]
    memory_id = conn.execute(
        """INSERT INTO memories(scope, owner, type, content, importance, source, status, use_count,
               content_hash, embedding, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (scope, owner, "summary", content, 2, source, "active", 0, digest,
         embedding_json(content), db.iso(), db.iso()),
    ).lastrowid
    return memory_id


def mark_used(conn, ids: list[int]) -> None:
    now = db.iso()
    for memory_id in ids:
        conn.execute("UPDATE memories SET use_count=use_count+1, last_used_at=?, updated_at=? WHERE id=?",
                     (now, now, memory_id))


ROUTES = [
    ("GET", re.compile(r"^/api/memories$"), list_memories),
    ("GET", re.compile(r"^/api/memories/search$"), search_memories),
    ("POST", re.compile(r"^/api/memories$"), create_memory),
    ("PUT", re.compile(r"^/api/memories/(?P<id>\d+)$"), update_memory),
    ("DELETE", re.compile(r"^/api/memories/(?P<id>\d+)$"), delete_memory),
]
