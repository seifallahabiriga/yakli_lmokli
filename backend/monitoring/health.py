from fastapi.responses import JSONResponse
from sqlalchemy import text

from db.session import async_engine
from queue.redis_client import async_redis_cache


async def build_health_response() -> JSONResponse:
    """
    Checks DB and Redis reachability.
    Returns 200 if all healthy, 503 if any dependency is down.
    Each check is independent — a Redis failure won't mask a DB failure.
    """
    checks: dict[str, dict] = {}
    healthy = True

    # PostgreSQL
    try:
        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["postgres"] = {"status": "ok"}
    except Exception as exc:
        checks["postgres"] = {"status": "error", "detail": str(exc)}
        healthy = False

    # Redis
    try:
        await async_redis_cache.ping()
        checks["redis"] = {"status": "ok"}
    except Exception as exc:
        checks["redis"] = {"status": "error", "detail": str(exc)}
        healthy = False

    status_code = 200 if healthy else 503
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "healthy" if healthy else "degraded",
            "checks": checks,
        },
    )