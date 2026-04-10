"""
Producer — the FastAPI side of the queue boundary.

Rules:
  - Routes and services NEVER import from workers.tasks directly.
  - They call functions in this module, which enqueue the task via .delay() or .apply_async().
  - This keeps the import graph clean: FastAPI → producer → Celery → workers.

Every function returns the Celery AsyncResult so callers can
optionally track task state via GET /tasks/{task_id}.
"""

from celery.result import AsyncResult

from queue.celery_app import celery_app


# =============================================================================
# Scraping
# =============================================================================

def enqueue_internship_scraper() -> AsyncResult:
    return celery_app.send_task(
        "workers.tasks.run_internship_scraper",
        queue="scraping",
    )


def enqueue_scholarship_scraper() -> AsyncResult:
    return celery_app.send_task(
        "workers.tasks.run_scholarship_scraper",
        queue="scraping",
    )


def enqueue_project_scraper() -> AsyncResult:
    return celery_app.send_task(
        "workers.tasks.run_project_scraper",
        queue="scraping",
    )


def enqueue_certification_scraper() -> AsyncResult:
    return celery_app.send_task(
        "workers.tasks.run_certification_scraper",
        queue="scraping",
    )


def enqueue_postdoc_scraper() -> AsyncResult:
    return celery_app.send_task(
        "workers.tasks.run_postdoc_scraper",
        queue="scraping",
    )


def enqueue_all_scrapers() -> list[AsyncResult]:
    """Triggers all observer agents at once — useful for admin 'refresh now' button."""
    return [
        enqueue_internship_scraper(),
        enqueue_scholarship_scraper(),
        enqueue_project_scraper(),
        enqueue_certification_scraper(),
        enqueue_postdoc_scraper(),
    ]


# =============================================================================
# ML / Analysis
# =============================================================================

def enqueue_classifier() -> AsyncResult:
    """Classifies all DRAFT opportunities that don't yet have an embedding."""
    return celery_app.send_task(
        "workers.tasks.run_classifier",
        queue="ml",
    )


def enqueue_cluster_recompute() -> AsyncResult:
    """Triggers a full cluster recompute cycle."""
    return celery_app.send_task(
        "workers.tasks.run_cluster_recompute",
        queue="ml",
    )


def enqueue_persist_faiss_index() -> AsyncResult:
    """Serializes the in-memory FAISS index to disk on demand."""
    return celery_app.send_task(
        "workers.tasks.persist_faiss_index",
        queue="ml",
    )


def enqueue_recommendation_recompute(user_id: int | None = None) -> AsyncResult:
    """
    Triggers recommendation recompute.

    Args:
        user_id: If provided, recomputes only for that user (on profile update).
                 If None, recomputes for all active users (scheduled run).
    """
    return celery_app.send_task(
        "workers.tasks.run_recommendation_recompute",
        args=[user_id],
        queue="ml",
    )


def enqueue_opportunity_embedding(opportunity_id: int) -> AsyncResult:
    """
    Embeds a single newly scraped opportunity immediately.
    Called by the opportunity service right after a new opportunity is saved,
    rather than waiting for the next scheduled classifier run.
    """
    return celery_app.send_task(
        "workers.tasks.embed_single_opportunity",
        args=[opportunity_id],
        queue="ml",
    )


# =============================================================================
# Notifications
# =============================================================================

def enqueue_deadline_reminders() -> AsyncResult:
    return celery_app.send_task(
        "workers.tasks.send_deadline_reminders",
        queue="notifications",
    )


def enqueue_new_opportunity_notifications(opportunity_id: int) -> AsyncResult:
    """
    Notifies relevant users about a newly published opportunity.
    Called by the opportunity service after status transitions to ACTIVE.
    """
    return celery_app.send_task(
        "workers.tasks.notify_new_opportunity",
        args=[opportunity_id],
        queue="notifications",
    )


def enqueue_recommendation_notification(
    user_id: int, recommendation_id: int
) -> AsyncResult:
    return celery_app.send_task(
        "workers.tasks.notify_new_recommendation",
        args=[user_id, recommendation_id],
        queue="notifications",
    )


# =============================================================================
# Maintenance
# =============================================================================

def enqueue_expire_opportunities() -> AsyncResult:
    return celery_app.send_task(
        "workers.tasks.expire_past_deadline_opportunities",
        queue="default",
    )


def enqueue_cleanup_notifications() -> AsyncResult:
    return celery_app.send_task(
        "workers.tasks.cleanup_archived_notifications",
        queue="default",
    )


# =============================================================================
# Task status
# =============================================================================

def get_task_status(task_id: str) -> dict:
    """
    Returns the current state of a Celery task by ID.
    Used by GET /tasks/{task_id} to let the frontend poll long-running jobs.
    """
    result = AsyncResult(task_id, app=celery_app)
    payload: dict = {
        "task_id": task_id,
        "status": result.status,
    }
    if result.ready():
        if result.successful():
            payload["result"] = result.result
        else:
            payload["error"] = str(result.result)
    return payload