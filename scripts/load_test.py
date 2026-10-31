#!/usr/bin/env python
"""轻量压测/基线：stdlib 并发请求，输出 QPS、P50/P95/P99、错误码分布。

用法：
  python scripts/load_test.py --base-url http://127.0.0.1:8090 \
      --username u_admin --password medagent123 --path /api/apps \
      --requests 200 --concurrency 10 --out data/load-baseline.json
"""
from __future__ import annotations

import argparse
import json
import statistics
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def call(base: str, method: str, path: str, token: str | None = None, body=None):
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    request = urllib.request.Request(base.rstrip("/") + path, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("Authorization", "Bearer " + token)
    started = time.perf_counter()
    status = 0
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            response.read()
            status = response.status
    except urllib.error.HTTPError as exc:
        exc.read()
        status = exc.code
    except Exception:  # noqa: BLE001
        status = -1
    return status, (time.perf_counter() - started) * 1000


def percentile(values, q):
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((q / 100.0) * (len(ordered) - 1)))))
    return round(ordered[index], 2)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="MediAgent 压测基线")
    parser.add_argument("--base-url", default="http://127.0.0.1:8090")
    parser.add_argument("--username", default="u_admin")
    parser.add_argument("--password", default="medagent123")
    parser.add_argument("--path", default="/api/apps")
    parser.add_argument("--requests", type=int, default=200)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--out", default="")
    args = parser.parse_args(argv)

    data = json.dumps({"username": args.username, "password": args.password}).encode("utf-8")
    request = urllib.request.Request(args.base_url.rstrip("/") + "/api/auth/login", data=data, method="POST",
                                     headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            token = json.loads(response.read().decode("utf-8"))["token"]
    except urllib.error.HTTPError as exc:
        print(f"登录失败：HTTP {exc.code}")
        return 2

    started = time.perf_counter()
    results = []
    with ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as pool:
        futures = [pool.submit(call, args.base_url, "GET", args.path, token) for _ in range(args.requests)]
        for future in futures:
            results.append(future.result())
    elapsed = max(0.001, time.perf_counter() - started)
    latencies = [latency for _, latency in results]
    codes: dict[str, int] = {}
    for code, _ in results:
        codes[str(code)] = codes.get(str(code), 0) + 1
    report = {
        "base_url": args.base_url,
        "path": args.path,
        "requests": args.requests,
        "concurrency": args.concurrency,
        "elapsed_s": round(elapsed, 3),
        "qps": round(args.requests / elapsed, 2),
        "latency_ms": {
            "min": round(min(latencies), 2) if latencies else 0,
            "p50": percentile(latencies, 50),
            "p95": percentile(latencies, 95),
            "p99": percentile(latencies, 99),
            "max": round(max(latencies), 2) if latencies else 0,
            "mean": round(statistics.mean(latencies), 2) if latencies else 0,
        },
        "status_codes": codes,
        "errors": sum(count for code, count in codes.items() if not code.startswith("2")),
        "note": "本机基线，非生产容量承诺；生产压测须在目标网络/数据量/并发下重跑",
    }
    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    return 0 if report["errors"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
