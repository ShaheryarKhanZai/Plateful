"""A tiny in-memory rate limiter (sliding window).

LOCAL LIMITATION: counters live in this one process. They reset on restart and are
not shared between several server workers. For production, use a shared store such as
Redis (or rate limit at your reverse proxy). Behind a proxy, request.client.host is the
proxy's address, so configure trusted proxy headers properly first.
"""
import threading
import time
from collections import defaultdict, deque

from fastapi import Request

from app.config import get_settings
from app.errors import AppError


class RateLimiter:
    def __init__(self, limit: int, window_seconds: int):
        self.limit, self.window = limit, window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        if not get_settings().rate_limit_enabled:
            return
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                retry = int(self.window - (now - hits[0])) + 1
                raise AppError(429, "rate_limited", "Too many attempts. Please wait and try again.",
                               {"Retry-After": str(retry)})
            hits.append(now)
            if len(self._hits) > 10_000:  # simple memory guard
                self._hits = defaultdict(deque, {k: v for k, v in self._hits.items() if v})

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()

    def by_ip(self, name: str):
        """FastAPI dependency: limit per client IP."""
        def dependency(request: Request) -> None:
            self.check(f"{name}:{request.client.host if request.client else 'unknown'}")
        return dependency


login_limiter = RateLimiter(limit=10, window_seconds=60)         # per IP
login_email_limiter = RateLimiter(limit=8, window_seconds=600)   # per email
register_limiter = RateLimiter(limit=5, window_seconds=3600)     # per IP
refresh_limiter = RateLimiter(limit=60, window_seconds=60)       # per IP
ALL_LIMITERS = [login_limiter, login_email_limiter, register_limiter, refresh_limiter]
