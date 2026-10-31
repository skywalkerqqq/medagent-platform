"""MediAgent 医疗 AI 中台 v1.1 · 零依赖 HTTP 服务。

启动：
    python server/app.py --port 8090 --db data/medagent.db --reset
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parent
ROOT = SERVER_DIR.parent
sys.path.insert(0, str(SERVER_DIR))

import auth  # noqa: E402
import common  # noqa: E402
import db  # noqa: E402
import handlers  # noqa: E402
import ratelimit  # noqa: E402
import seed  # noqa: E402

WEB_DIR = ROOT / "web"
DB_PATH = ROOT / "data" / "medagent.db"
PUBLIC = set(auth.PUBLIC_PATHS) | {"/api/health"}
MAX_BODY = 1024 * 1024
LIMITER = ratelimit.Limiter.from_env()


class Handler(BaseHTTPRequestHandler):
    server_version = "MediAgent/1.1"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        return

    # ---------------------------------------------------------------- http
    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")

    def do_PUT(self):
        self._handle("PUT")

    def do_DELETE(self):
        self._handle("DELETE")

    def _handle(self, method: str):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if not path.startswith("/api/"):
            self._static(path)
            return
        headers_lower = {key.lower(): value for key, value in self.headers.items()}
        if path.rstrip("/") != "/api/health" and LIMITER.enabled:
            key = LIMITER.client_key(self.client_address[0], headers_lower)
            allowed, retry_after = LIMITER.allow(key)
            if not allowed:
                self._json(429, {"error": {"code": "rate_limited", "message": "请求过于频繁，请稍后重试"}},
                           {"Retry-After": str(retry_after)})
                return
        query = dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=False))
        body = {}
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            self._json(413, {"error": {"code": "payload_too_large", "message": "请求体超过 1MB"}})
            return
        if method in ("POST", "PUT", "DELETE") and length:
            raw = self.rfile.read(length)
            try:
                body = json.loads(raw.decode("utf-8")) if raw else {}
            except (ValueError, UnicodeDecodeError):
                self._json(400, {"error": {"code": "invalid_json", "message": "请求体不是合法 JSON"}})
                return
            if not isinstance(body, dict):
                self._json(400, {"error": {"code": "invalid_json", "message": "请求体必须是 JSON 对象"}})
                return
        conn = db.connect(DB_PATH)
        try:
            user = None
            if path.rstrip("/") not in PUBLIC:
                token = auth.bearer(headers_lower)
                user = auth.token_user(conn, token)
                if user is None:
                    self._json(401, {"error": {"code": "unauthorized", "message": "未登录或会话已过期"}})
                    return
            ctx = {
                "conn": conn,
                "user": user,
                "headers": headers_lower,
                "query": query,
                "body": body,
                "params": {},
            }
            status, payload = handlers.dispatch(method, path, ctx)
            self._json(status, payload)
        except common.ApiError as exc:
            detail = {"code": exc.code, "message": exc.message}
            if exc.details:
                detail["details"] = exc.details
            self._json(exc.status, {"error": detail})
        except Exception:  # noqa: BLE001 - 不向客户端泄露堆栈
            traceback.print_exc()
            self._json(500, {"error": {"code": "internal_error", "message": "服务器内部错误，请查看服务端日志"}})
        finally:
            conn.close()

    def _json(self, status: int, payload, extra_headers: dict | None = None):
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        if (os.environ.get("ENABLE_HSTS") or "") in ("1", "true", "yes"):
            self.send_header("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        for key, value in (extra_headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(raw)

    def _static(self, path: str):
        rel = path.lstrip("/")
        if rel in ("", "index.html") or "." not in Path(rel).name:
            target = WEB_DIR / "index.html"
        else:
            target = (WEB_DIR / rel).resolve()
            try:
                target.relative_to(WEB_DIR.resolve())
            except ValueError:
                self._json(404, {"error": {"code": "not_found", "message": "文件不存在"}})
                return
        if not target.exists():
            if path in ("/", "/index.html"):
                self._json(500, {"error": {"code": "frontend_missing", "message": "前端文件缺失"}})
            else:
                self._json(404, {"error": {"code": "not_found", "message": "文件不存在"}})
            return
        content = target.read_bytes()
        content_type = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "text/javascript; charset=utf-8",
            ".json": "application/json; charset=utf-8",
            ".svg": "image/svg+xml",
            ".png": "image/png",
        }.get(target.suffix.lower(), "application/octet-stream")
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(content)


def main(argv=None) -> int:
    global DB_PATH
    parser = argparse.ArgumentParser(description="MediAgent 医疗 AI 中台 v1.1")
    parser.add_argument("--port", type=int, default=8090)
    parser.add_argument("--db", default=str(DB_PATH))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args(argv)
    DB_PATH = Path(args.db).resolve()
    conn = db.init_db(DB_PATH, reset=args.reset)
    created = seed.seed(conn)
    conn.close()
    print(f"MediAgent v1.1 数据库: {DB_PATH} {'（已重置并写入种子）' if args.reset else ('（首次写入种子）' if created else '（已存在）')}")
    if not (WEB_DIR / "index.html").exists():
        print("警告：web/index.html 不存在，API 可用但前端不可用")
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"服务已启动：http://{args.host}:{args.port}  （登录：u_creator / {seed.PASSWORD}）", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
