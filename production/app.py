"""MediAgent 生产化边缘（Stage 1）：FastAPI + Uvicorn，复用现有业务 handler。

重要边界：
- 本文件只替换 HTTP 边缘（FastAPI/ASGI、健康检查、安全响应头、请求 ID），
  业务仍调用 `server/handlers.py`，存储仍为 SQLite（持久化卷）；
- PostgreSQL 迁移是下一阶段（`deploy/postgres/schema.sql` 草案），本阶段不伪装已迁移；
- 单 worker 运行以避免 SQLite 并发写锁；水平扩展须先完成 PG/共享存储迁移。
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.parse
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent.parent
SERVER_DIR = ROOT / "server"
sys.path.insert(0, str(SERVER_DIR))

import auth  # noqa: E402
import common  # noqa: E402
import db  # noqa: E402
import handlers  # noqa: E402
import ratelimit  # noqa: E402
import seed  # noqa: E402

DB_PATH = Path(os.environ.get("MEDAGENT_DB", str(ROOT / "data" / "medagent.db"))).resolve()
WEB_DIR = Path(os.environ.get("MEDAGENT_WEB", str(ROOT / "web"))).resolve()
PUBLIC = set(auth.PUBLIC_PATHS) | {"/api/health"}
MAX_BODY = 1024 * 1024
VERSION = "1.1.0-prod-stage1"
LIMITER = ratelimit.Limiter.from_env()


@asynccontextmanager
async def lifespan(app: FastAPI):
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = db.init_db(DB_PATH)  # type: ignore[arg-type]
    seed.seed(conn)
    conn.close()
    yield


app = FastAPI(title="MediAgent 医疗 AI 中台（生产边缘 Stage 1）",
              version=VERSION, docs_url=None, redoc_url=None, openapi_url=None,
              lifespan=lifespan)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    request_id = request.headers.get("X-Request-Id") or uuid.uuid4().hex[:16]
    started = time.time()
    if LIMITER.enabled and request.url.path.rstrip("/") != "/api/health":
        client = request.client.host if request.client else "unknown"
        key = LIMITER.client_key(client, {key.lower(): value for key, value in request.headers.items()})
        allowed, retry_after = LIMITER.allow(key)
        if not allowed:
            response = JSONResponse(status_code=429,
                                    content={"error": {"code": "rate_limited", "message": "请求过于频繁，请稍后重试"}})
            response.headers["Retry-After"] = str(retry_after)
            response.headers["X-Request-Id"] = request_id
            return response
    response = await call_next(request)
    response.headers["X-Request-Id"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = response.headers.get("Cache-Control", "no-store")
    response.headers["X-Process-Time"] = f"{int((time.time() - started) * 1000)}ms"
    return response


@app.get("/healthz")
def healthz():
    return {"status": "ok", "version": VERSION}


@app.get("/readyz")
def readyz():
    try:
        conn = db.connect(DB_PATH)  # type: ignore[arg-type]
        try:
            conn.execute("SELECT 1").fetchone()
        finally:
            conn.close()
    except Exception:  # noqa: BLE001
        return JSONResponse(status_code=503, content={"status": "not_ready"})
    return {"status": "ready", "db": "sqlite"}


async def _api(request: Request, method: str) -> JSONResponse:
    parsed = urllib.parse.urlparse(str(request.url))
    path = parsed.path
    query = dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=False))
    raw = await request.body()
    if len(raw) > MAX_BODY:
        return JSONResponse(status_code=413,
                            content={"error": {"code": "payload_too_large", "message": "请求体超过 1MB"}})
    body = {}
    if method in ("POST", "PUT", "DELETE") and raw:
        try:
            body = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return JSONResponse(status_code=400,
                                content={"error": {"code": "invalid_json", "message": "请求体不是合法 JSON"}})
        if not isinstance(body, dict):
            return JSONResponse(status_code=400,
                                content={"error": {"code": "invalid_json", "message": "请求体必须是 JSON 对象"}})
    conn = db.connect(DB_PATH)  # type: ignore[arg-type]
    headers_lower = {key.lower(): value for key, value in request.headers.items()}
    try:
        user = None
        if path.rstrip("/") not in PUBLIC:
            token = auth.bearer(headers_lower)
            user = auth.token_user(conn, token)
            if user is None:
                return JSONResponse(status_code=401,
                                    content={"error": {"code": "unauthorized", "message": "未登录或会话已过期"}})
        ctx = {"conn": conn, "user": user, "headers": headers_lower,
               "query": query, "body": body, "params": {}}
        status, payload = handlers.dispatch(method, path, ctx)
        return JSONResponse(status_code=status, content=payload)
    except common.ApiError as exc:
        detail = {"code": exc.code, "message": exc.message}
        if exc.details:
            detail["details"] = exc.details
        return JSONResponse(status_code=exc.status, content={"error": detail})
    finally:
        conn.close()


@app.get("/api/{path:path}")
async def api_get(request: Request, path: str):
    return await _api(request, "GET")


@app.post("/api/{path:path}")
async def api_post(request: Request, path: str):
    return await _api(request, "POST")


@app.put("/api/{path:path}")
async def api_put(request: Request, path: str):
    return await _api(request, "PUT")


@app.delete("/api/{path:path}")
async def api_delete(request: Request, path: str):
    return await _api(request, "DELETE")


if WEB_DIR.exists():
    app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
