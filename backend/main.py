"""
main.py — FastAPI application entry point.

Owns:
  - App instantiation and metadata
  - Lifespan: DB + Redis startup verification and graceful shutdown
  - Exception handlers: maps domain exceptions to HTTP responses
  - Middleware: CORS, rate limiting, request logging
  - Router registration
  - Health and task-status endpoints
"""

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.api.routes import auth, cluster, notification, opportunity, recommendation, user
from backend.core.config import get_settings
from backend.core.exceptions import ObservatoryException
from backend.db.session import close_db, init_db
from backend.middleware.rate_limiter import RateLimiterMiddleware
from backend.monitoring.health import build_health_response
from backend.monitoring.metrics import http_request_counter, http_request_duration
from backend.queue.producer import get_task_status
from backend.queue.redis_client import close_redis, init_redis

settings = get_settings()
logger = logging.getLogger(__name__)


# =============================================================================
# Lifespan
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup: verify DB + Redis are reachable before accepting traffic.
    Shutdown: gracefully close connection pools.
    """
    logger.info("Starting %s v%s [%s]", settings.APP_NAME, settings.APP_VERSION, settings.ENVIRONMENT)

    await init_db()
    logger.info("PostgreSQL connection verified")

    await init_redis()
    logger.info("Redis connection verified")

    yield

    await close_db()
    await close_redis()
    logger.info("Connections closed — shutdown complete")


# =============================================================================
# App
# =============================================================================

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "Multi-Agent System for Internship, Project, "
        "Certification, and Scholarship Management"
    ),
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
    lifespan=lifespan,
)


# =============================================================================
# Middleware
# =============================================================================

# CORS — tighten origins for production
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting
app.add_middleware(RateLimiterMiddleware)


@app.middleware("http")
async def request_logging_and_metrics(request: Request, call_next):
    """
    Logs every request with method, path, status, and duration.
    Increments Prometheus-style counters if metrics are enabled.
    """
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000

    logger.info(
        "%s %s %d %.1fms",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )

    if settings.METRICS_ENABLED:
        http_request_counter.labels(
            method=request.method,
            path=request.url.path,
            status=response.status_code,
        ).inc()
        http_request_duration.labels(
            method=request.method,
            path=request.url.path,
        ).observe(duration_ms / 1000)

    return response


# =============================================================================
# Exception handlers
# =============================================================================

@app.exception_handler(ObservatoryException)
async def observatory_exception_handler(
    request: Request,
    exc: ObservatoryException,
):
    """
    Single handler for all domain exceptions.
    Maps exc.status_code → HTTP status, returns consistent JSON shape.
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.__class__.__name__,
            "message": exc.message,
            "detail": exc.detail,
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Catches anything that slipped through — prevents raw 500 tracebacks."""
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "error": "InternalError",
            "message": "An unexpected error occurred.",
            "detail": None,
        },
    )


# =============================================================================
# Routers
# =============================================================================

API_PREFIX = settings.API_PREFIX   # "/api/v1"

app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(user.router, prefix=API_PREFIX)
app.include_router(opportunity.router, prefix=API_PREFIX)
app.include_router(recommendation.router, prefix=API_PREFIX)
app.include_router(notification.router, prefix=API_PREFIX)
app.include_router(cluster.router, prefix=API_PREFIX)


# =============================================================================
# System endpoints — no prefix, no auth
# =============================================================================

@app.get(settings.HEALTH_CHECK_PATH, tags=["system"], summary="Health check")
async def health():
    """
    Returns DB and Redis reachability.
    Used by Docker Compose / load balancer health probes.
    """
    return await build_health_response()


@app.get(
    "/tasks/{task_id}",
    tags=["system"],
    summary="Poll the status of an async Celery task",
)
async def task_status(task_id: str):
    """
    Lets the frontend poll long-running jobs (recompute, scrape triggers).
    Returns status, and result/error when the task is complete.
    """
    return get_task_status(task_id)


@app.get("/", tags=["system"], include_in_schema=False)
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs" if settings.DEBUG else "disabled",
    }