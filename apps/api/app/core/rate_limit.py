from __future__ import annotations

import hashlib
import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from redis.asyncio import Redis
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from apps.api.app.core.config import settings


class LocalSlidingWindow:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def hit(self, key: str, *, limit: int, window: int) -> tuple[bool, int]:
        now = time.monotonic()
        cutoff = now - window
        bucket = self._hits[key]
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        if len(bucket) >= limit:
            return False, 0
        bucket.append(now)
        return True, max(limit - len(bucket), 0)


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self.local = LocalSlidingWindow()

    @staticmethod
    def _key(request: Request) -> str:
        authorization = request.headers.get("authorization", "")
        identity = authorization or (request.client.host if request.client else "unknown")
        return hashlib.sha256(identity.encode("utf-8")).hexdigest()

    async def _redis_hit(self, key: str) -> tuple[bool, int] | None:
        client = Redis.from_url(settings.redis_url, socket_connect_timeout=0.15)
        redis_key = f"rate-limit:{key}:{int(time.time()) // settings.rate_limit_window_seconds}"
        try:
            count = await client.incr(redis_key)
            if count == 1:
                await client.expire(redis_key, settings.rate_limit_window_seconds + 1)
            return count <= settings.rate_limit_requests, max(
                settings.rate_limit_requests - count, 0
            )
        except Exception:
            return None
        finally:
            await client.aclose()

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if (
            settings.rate_limit_requests <= 0
            or request.url.path.endswith("/health")
            or request.url.path.endswith("/openapi.json")
        ):
            return await call_next(request)
        key = self._key(request)
        result = await self._redis_hit(key)
        if result is None:
            result = self.local.hit(
                key,
                limit=settings.rate_limit_requests,
                window=settings.rate_limit_window_seconds,
            )
        allowed, remaining = result
        if not allowed:
            return Response(
                content='{"detail":"请求过于频繁，请稍后重试"}',
                status_code=429,
                media_type="application/json",
                headers={"Retry-After": str(settings.rate_limit_window_seconds)},
            )
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(settings.rate_limit_requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response
