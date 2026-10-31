"""轻量限流（令牌桶）：stdlib 服务与 FastAPI 边缘共用。

- 默认关闭（RATE_LIMIT_RPS=0），生产在编排层显式开启；
- 按客户端 IP 限流；只有 TRUST_PROXY=1 时才信任 X-Forwarded-For（防止伪造绕过）；
- 单进程内存桶：多副本需换 Redis 令牌桶（下一阶段）。
"""
from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass


@dataclass
class _Bucket:
    tokens: float
    updated: float


class Limiter:
    def __init__(self, rate: float = 0.0, burst: int = 0, trust_proxy: bool = False):
        self.rate = max(0.0, float(rate or 0))
        self.burst = max(1, int(burst or max(1, self.rate)))
        self.trust_proxy = trust_proxy
        self._buckets: dict[str, _Bucket] = {}
        self._lock = threading.Lock()

    @property
    def enabled(self) -> bool:
        return self.rate > 0

    @classmethod
    def from_env(cls) -> "Limiter":
        rate = float(os.environ.get("RATE_LIMIT_RPS") or 0)
        burst = int(os.environ.get("RATE_LIMIT_BURST") or 0)
        trust = (os.environ.get("TRUST_PROXY") or "").strip() in ("1", "true", "yes")
        return cls(rate=rate, burst=burst, trust_proxy=trust)

    def client_key(self, remote_addr: str, headers: dict) -> str:
        if self.trust_proxy:
            forwarded = headers.get("x-forwarded-for") or headers.get("X-Forwarded-For") or ""
            if forwarded:
                return forwarded.split(",")[0].strip()
        return remote_addr or "unknown"

    def allow(self, key: str) -> tuple[bool, float]:
        """返回 (是否允许, 建议 Retry-After 秒)。"""
        if not self.enabled:
            return True, 0.0
        now = time.monotonic()
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                bucket = _Bucket(tokens=float(self.burst), updated=now)
                self._buckets[key] = bucket
            elapsed = max(0.0, now - bucket.updated)
            bucket.tokens = min(float(self.burst), bucket.tokens + elapsed * self.rate)
            bucket.updated = now
            if bucket.tokens >= 1.0:
                bucket.tokens -= 1.0
                allowed = True
            else:
                allowed = False
            retry_after = 0.0 if allowed else max(0.1, (1.0 - bucket.tokens) / self.rate)
            # 防止桶无限增长（攻击者伪造大量 IP）
            if len(self._buckets) > 20000:
                self._buckets.clear()
            return allowed, round(retry_after, 2)
