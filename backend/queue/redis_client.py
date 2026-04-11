from collections.abc import AsyncGenerator

import redis.asyncio as aioredis
from redis import Redis

from backend.core.config import get_settings

settings = get_settings()

# =============================================================================
# Async clients — FastAPI route handlers and services
# =============================================================================

# Cache (db 2) — opportunity lists, recommendations, cluster assignments
async_redis_cache: aioredis.Redis = aioredis.from_url(
    settings.REDIS_CACHE_URL,
    encoding="utf-8",
    decode_responses=True,
    max_connections=20,
)


async def get_async_redis() -> AsyncGenerator[aioredis.Redis, None]:
    """
    FastAPI dependency — yields the async Redis cache client.

    Usage:
        async def my_route(cache: aioredis.Redis = Depends(get_async_redis)): ...
    """
    try:
        yield async_redis_cache
    finally:
        pass  # connection returns to the pool automatically


# =============================================================================
# Sync clients — Celery tasks
# =============================================================================

# Cache (db 2) — same logical db as async client, sync interface for workers
sync_redis_cache: Redis = Redis.from_url(
    settings.REDIS_CACHE_URL,
    encoding="utf-8",
    decode_responses=True,
    max_connections=20,
)


def get_sync_redis() -> Redis:
    """
    Returns the shared sync Redis cache client for Celery tasks.

    Reuse the same instance — do not close it manually.

    Usage:
        cache = get_sync_redis()
        cache.setex("key", 3600, "value")
    """
    return sync_redis_cache


# =============================================================================
# Lifecycle helpers — called from FastAPI lifespan in main.py
# =============================================================================

async def init_redis() -> None:
    """Verifies the async Redis connection is reachable at startup."""
    await async_redis_cache.ping()


async def close_redis() -> None:
    """Closes the async Redis connection pool on shutdown."""
    await async_redis_cache.aclose()


# =============================================================================
# Cache key builders — centralised so keys are consistent everywhere
# =============================================================================

class CacheKeys:
    """
    Namespace for all Redis cache key patterns.

    Using a class instead of scattered f-strings prevents typos and makes
    it trivial to find every place a key is used.
    """

    @staticmethod
    def opportunities_list(page: int, page_size: int, filters_hash: str) -> str:
        return f"opportunities:list:{page}:{page_size}:{filters_hash}"

    @staticmethod
    def opportunity_detail(opportunity_id: int) -> str:
        return f"opportunities:detail:{opportunity_id}"

    @staticmethod
    def user_recommendations(user_id: int) -> str:
        return f"recommendations:user:{user_id}"

    @staticmethod
    def cluster_list() -> str:
        return "clusters:all"

    @staticmethod
    def cluster_members(cluster_id: int) -> str:
        return f"clusters:members:{cluster_id}"

    @staticmethod
    def user_profile(user_id: int) -> str:
        return f"users:profile:{user_id}"