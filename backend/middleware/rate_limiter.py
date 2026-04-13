"""
Rate limiter middleware — sliding window via Redis.

Algorithm:
  - Key: rate_limit:{client_ip}
  - On each request: INCR the key, set TTL on first request.
  - If count > RATE_LIMIT_REQUESTS within the window → 429.
  - Uses sync Redis from the module-level client (middleware is sync-friendly).

Falls back gracefully if Redis is unreachable — allows the request
rather than taking down the API when the cache is temporarily unavailable.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from backend.core.config import get_settings

settings = get_settings()

# Paths exempt from rate limiting
_EXEMPT_PATHS = {
    settings.HEALTH_CHECK_PATH,
    "/",
    "/docs",
    "/redoc",
    "/openapi.json",
}


class RateLimiterMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in _EXEMPT_PATHS:
            return await call_next(request)

        client_ip = self._get_client_ip(request)
        key = f"rate_limit:{client_ip}"

        try:
            from backend.queue.redis_client import async_redis_cache as cache

            count = await cache.incr(key)

            # Set TTL only on first request in the window
            if count == 1:
                await cache.expire(key, settings.RATE_LIMIT_WINDOW_SECONDS)

            if count > settings.RATE_LIMIT_REQUESTS:
                ttl = await cache.ttl(key)
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "RateLimitError",
                        "message": "Too many requests.",
                        "detail": {
                            "limit": settings.RATE_LIMIT_REQUESTS,
                            "window_seconds": settings.RATE_LIMIT_WINDOW_SECONDS,
                            "retry_after": ttl,
                        },
                    },
                    headers={"Retry-After": str(ttl)},
                )

        except Exception:
            # Redis unavailable — fail open rather than blocking all traffic
            pass

        return await call_next(request)

    @staticmethod
    def _get_client_ip(request: Request) -> str:
        """
        Extracts real client IP, respecting X-Forwarded-For when behind a proxy.
        Falls back to request.client.host for direct connections.
        """
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        if request.client:
            return request.client.host
        return "unknown"