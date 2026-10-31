"""知识来源登记与增量同步（文件/JSON/URL）。

- 文件/JSON 路径限制在数据库所在目录（data/）内，拒绝目录穿越；
- 同步导入为 pending 知识，仍需知识审核后生效（不绕过审核）；
- 相同标题+来源已存在则跳过（幂等同步，避免重复导入）；
- URL 仅支持纯文本/JSON（真实站点需白名单、鉴权与内容清洗，POC 边界）。
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from pathlib import Path

import common
import db

TIMEOUT = 15


def _base_dir() -> Path:
    if db.DB_PATH:
        return Path(db.DB_PATH).resolve().parent
    return Path(__file__).resolve().parent.parent / "data"


def _source_json(row) -> dict:
    data = dict(row)
    data["scope"] = common.loads(data.get("scope"), []) or []
    data["enabled"] = bool(data.get("enabled"))
    return data


def _resolve(location: str) -> Path:
    raw = str(location or "").strip()
    if not raw:
        raise common.ApiError(400, "validation", "location 不能为空")
    base = _base_dir().resolve()
    if raw.startswith(("http://", "https://")):
        raise common.ApiError(400, "validation", "URL 来源请使用 kind=url")
    path = (base / raw).resolve()
    if base != path and base not in path.parents:
        raise common.ApiError(400, "invalid_path", "来源路径必须位于 data/ 目录内（拒绝目录穿越）")
    return path


def _docs_from_file(path: Path) -> list[dict]:
    if not path.is_file():
        raise common.ApiError(404, "source_not_found", f"来源文件不存在：{path.name}")
    text = path.read_text(encoding="utf-8", errors="replace")
    title = path.stem
    for line in text.splitlines():
        stripped = line.strip().lstrip("#").strip()
        if stripped:
            title = stripped[:60]
            break
    return [{"title": title, "content": text, "owner": "来源同步"}]


def _docs_from_json(path: Path) -> list[dict]:
    if not path.is_file():
        raise common.ApiError(404, "source_not_found", f"来源文件不存在：{path.name}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise common.ApiError(400, "invalid_source", f"JSON 解析失败：{exc}") from exc
    if not isinstance(data, list):
        raise common.ApiError(400, "invalid_source", "JSON 来源必须是文档数组")
    docs = []
    for item in data:
        if not isinstance(item, dict) or not item.get("title") or not item.get("content"):
            continue
        docs.append({
            "title": str(item["title"])[:120],
            "content": str(item["content"]),
            "owner": str(item.get("owner") or "来源同步"),
            "source": str(item.get("source") or ""),
        })
    return docs


def _docs_from_url(location: str) -> list[dict]:
    request = urllib.request.Request(location, headers={"User-Agent": "MediAgent-Sync/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            text = response.read().decode("utf-8", "replace")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
        raise common.ApiError(502, "source_upstream", f"来源拉取失败：{exc}") from exc
    text = re.sub(r"<script.*?</script>|<style.*?</style>", "", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        raise common.ApiError(400, "invalid_source", "来源内容为空")
    return [{"title": location[:80], "content": text[:5000], "owner": "来源同步"}]


def list_sources(ctx):
    common.require(ctx["user"], "knowledge:read")
    rows = ctx["conn"].execute("SELECT * FROM knowledge_sources ORDER BY id").fetchall()
    return 200, {"items": [_source_json(row) for row in rows]}


def create_source(ctx):
    conn, user, body = ctx["conn"], ctx["user"], ctx["body"]
    common.require(user, "knowledge:write", "仅知识运营/管理员可登记来源")
    name = common.str_field(body.get("name"), "name", required=True)
    kind = common.str_field(body.get("kind"), "kind", default="file").lower()
    if kind not in ("file", "json", "url"):
        raise common.ApiError(400, "validation", "kind 只能是 file/json/url")
    location = common.str_field(body.get("location"), "location", required=True)
    scope = body.get("scope") or ["公共"]
    if not isinstance(scope, list) or not scope:
        raise common.ApiError(400, "validation", "scope 必须是非空数组")
    if kind in ("file", "json"):
        _resolve(location)  # 提前校验路径（不要求文件已存在）
    source_id = conn.execute(
        "INSERT INTO knowledge_sources(name, kind, location, scope, enabled, created_by, created_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (name, kind, location, common.dumps(scope), 1 if body.get("enabled", True) else 0,
         user["id"], db.iso()),
    ).lastrowid
    common.audit(conn, user["id"], "登记知识来源", "knowledge_source", source_id, f"{name}（{kind}）")
    conn.commit()
    return 201, _source_json(conn.execute("SELECT * FROM knowledge_sources WHERE id=?", (source_id,)).fetchone())


def sync_source(ctx):
    conn, user = ctx["conn"], ctx["user"]
    common.require(user, "knowledge:write", "仅知识运营/管理员可同步来源")
    source = conn.execute("SELECT * FROM knowledge_sources WHERE id=?", (int(ctx["params"]["id"]),)).fetchone()
    if not source:
        raise common.ApiError(404, "not_found", "知识来源不存在")
    if not source["enabled"]:
        raise common.ApiError(409, "conflict", "来源已停用")
    kind = source["kind"]
    if kind == "file":
        docs = _docs_from_file(_resolve(source["location"]))
    elif kind == "json":
        docs = _docs_from_json(_resolve(source["location"]))
    else:
        docs = _docs_from_url(source["location"])
    scope = common.loads(source["scope"], []) or ["公共"]
    imported, skipped = 0, 0
    for doc in docs:
        title = doc["title"]
        exists = conn.execute(
            "SELECT 1 FROM knowledge_docs WHERE title=? AND source=?", (title, source["name"])).fetchone()
        if exists:
            skipped += 1
            continue
        code = "K-" + str(conn.execute("SELECT COUNT(*) AS c FROM knowledge_docs").fetchone()["c"] + 1).zfill(4)
        conn.execute(
            """INSERT INTO knowledge_docs(code, title, source, owner, scope, version, effective_at, expires_at,
                   status, content, created_by, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (code, title, source["name"], doc.get("owner") or "来源同步", common.dumps(scope), 1,
             db.iso(), "", "pending", doc["content"], user["id"], db.iso()),
        )
        imported += 1
    detail = f"导入 {imported} 条，跳过 {skipped} 条（待审核）"
    conn.execute("UPDATE knowledge_sources SET last_sync_at=?, last_status=?, last_detail=? WHERE id=?",
                 (db.iso(), "succeeded", detail, source["id"]))
    common.audit(conn, user["id"], "同步知识来源", "knowledge_source", source["id"], detail)
    conn.commit()
    return 200, {"ok": True, "imported": imported, "skipped": skipped,
                 "status": "succeeded", "detail": detail,
                 "note": "导入内容为 pending，需知识审核后生效"}


ROUTES = [
    ("GET", re.compile(r"^/api/knowledge/sources$"), list_sources),
    ("POST", re.compile(r"^/api/knowledge/sources$"), create_source),
    ("POST", re.compile(r"^/api/knowledge/sources/(?P<id>\d+)/sync$"), sync_source),
]
