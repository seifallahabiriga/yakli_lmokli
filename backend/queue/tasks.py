"""
Worker tasks — the Celery side of the queue boundary.

Rules:
  - Tasks are sync functions (Celery doesn't run an event loop by default).
  - DB access uses get_sync_db() + SyncSessionLocal.
  - Redis access uses get_sync_redis().
  - Heavy ML work is delegated to service/agent classes; tasks are thin wrappers.
  - Each task logs its start, success, and failure clearly.
"""

import logging
from datetime import UTC, datetime, timedelta

from celery import Task
from celery.exceptions import SoftTimeLimitExceeded

from queue.celery_app import celery_app

logger = logging.getLogger(__name__)


# =============================================================================
# Base task class — shared retry / error handling
# =============================================================================

class BaseTask(Task):
    """
    Custom base that adds structured logging and a clean retry policy.
    All tasks below use base=BaseTask.
    """
    abstract = True

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.error(
            "Task failed",
            extra={
                "task": self.name,
                "task_id": task_id,
                "error": str(exc),
                "traceback": str(einfo),
            },
        )

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        logger.warning(
            "Task retrying",
            extra={
                "task": self.name,
                "task_id": task_id,
                "error": str(exc),
            },
        )

    def on_success(self, retval, task_id, args, kwargs):
        logger.info(
            "Task succeeded",
            extra={"task": self.name, "task_id": task_id, "result": retval},
        )


# =============================================================================
# Helpers
# =============================================================================

def _get_db_and_cache():
    """Returns (sync_db_session, sync_redis_client) for use inside a task."""
    from db.session import get_sync_db
    from queue.redis_client import get_sync_redis
    return get_sync_db(), get_sync_redis()


# =============================================================================
# Scraping tasks — observer agents
# =============================================================================

@celery_app.task(
    base=BaseTask,
    name="workers.tasks.run_internship_scraper",
    bind=True,
    queue="scraping",
    max_retries=3,
    default_retry_delay=60,
)
def run_internship_scraper(self: Task) -> dict:
    db, cache = _get_db_and_cache()
    try:
        from workers.worker_app.job_runner import run_scraper_agent
        result = run_scraper_agent("internship", db, cache)
        db.commit()
        return result
    except SoftTimeLimitExceeded:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(
    base=BaseTask,
    name="workers.tasks.run_scholarship_scraper",
    bind=True,
    queue="scraping",
    max_retries=3,
    default_retry_delay=60,
)
def run_scholarship_scraper(self: Task) -> dict:
    db, cache = _get_db_and_cache()
    try:
        from workers.worker_app.job_runner import run_scraper_agent
        result = run_scraper_agent("scholarship", db, cache)
        db.commit()
        return result
    except SoftTimeLimitExceeded:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(
    base=BaseTask,
    name="workers.tasks.run_project_scraper",
    bind=True,
    queue="scraping",
    max_retries=3,
    default_retry_delay=60,
)
def run_project_scraper(self: Task) -> dict:
    db, cache = _get_db_and_cache()
    try:
        from workers.worker_app.job_runner import run_scraper_agent
        result = run_scraper_agent("project", db, cache)
        db.commit()
        return result
    except SoftTimeLimitExceeded:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(
    base=BaseTask,
    name="workers.tasks.run_certification_scraper",
    bind=True,
    queue="scraping",
    max_retries=3,
    default_retry_delay=60,
)
def run_certification_scraper(self: Task) -> dict:
    db, cache = _get_db_and_cache()
    try:
        from workers.worker_app.job_runner import run_scraper_agent
        result = run_scraper_agent("certification", db, cache)
        db.commit()
        return result
    except SoftTimeLimitExceeded:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(
    base=BaseTask,
    name="workers.tasks.run_postdoc_scraper",
    bind=True,
    queue="scraping",
    max_retries=3,
    default_retry_delay=60,
)
def run_postdoc_scraper(self: Task) -> dict:
    db, cache = _get_db_and_cache()
    try:
        from workers.worker_app.job_runner import run_scraper_agent
        result = run_scraper_agent("postdoc", db, cache)
        db.commit()
        return result
    except SoftTimeLimitExceeded:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise self.retry(exc=exc)
    finally:
        db.close()


# =============================================================================
# ML tasks — analysis agents
# =============================================================================

@celery_app.task(
    base=BaseTask,
    name="workers.tasks.run_classifier",
    bind=True,
    queue="ml",
    max_retries=2,
    default_retry_delay=120,
)
def run_classifier(self: Task) -> dict:
    """Embeds and classifies all DRAFT opportunities without embeddings."""
    db, cache = _get_db_and_cache()
    try:
        from workers.worker_app.job_runner import run_classifier_agent
        result = run_classifier_agent(db, cache)
        db.commit()
        return result
    except SoftTimeLimitExceeded:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(
    base=BaseTask,
    name="workers.tasks.embed_single_opportunity",
    bind=True,
    queue="ml",
    max_retries=2,
    default_retry_delay=30,
)
def embed_single_opportunity(self: Task, opportunity_id: int) -> dict:
    """Embeds a single opportunity immediately after scraping."""
    db, cache = _get_db_and_cache()
    try:
        from workers.worker_app.job_runner import embed_opportunity
        result = embed_opportunity(opportunity_id, db)
        db.commit()
        return result
    except SoftTimeLimitExceeded:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(
    base=BaseTask,
    name="workers.tasks.run_cluster_recompute",
    bind=True,
    queue="ml",
    max_retries=1,
    default_retry_delay=300,
)
def run_cluster_recompute(self: Task) -> dict:
    """Full cluster recompute: wipe clusters, re-cluster all embedded opportunities."""
    db, cache = _get_db_and_cache()
    try:
        from workers.worker_app.job_runner import run_cluster_agent
        result = run_cluster_agent(db, cache)
        db.commit()
        return result
    except SoftTimeLimitExceeded:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(
    base=BaseTask,
    name="workers.tasks.run_recommendation_recompute",
    bind=True,
    queue="ml",
    max_retries=1,
    default_retry_delay=120,
)
def run_recommendation_recompute(self: Task, user_id: int | None = None) -> dict:
    """
    Recomputes recommendations.
    user_id=None → all active users.
    user_id=N    → single user (triggered by profile update).
    """
    db, cache = _get_db_and_cache()
    try:
        from workers.worker_app.job_runner import run_recommendation_agent
        result = run_recommendation_agent(db, cache, user_id=user_id)
        db.commit()
        return result
    except SoftTimeLimitExceeded:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise self.retry(exc=exc)
    finally:
        db.close()


# =============================================================================
# Notification tasks
# =============================================================================

@celery_app.task(
    base=BaseTask,
    name="workers.tasks.send_deadline_reminders",
    bind=True,
    queue="notifications",
    max_retries=2,
    default_retry_delay=60,
)
def send_deadline_reminders(self: Task) -> dict:
    """Notifies users about opportunities expiring within 3 days."""
    db, cache = _get_db_and_cache()
    try:
        from workers.worker_app.job_runner import run_deadline_reminder_agent
        result = run_deadline_reminder_agent(db, cache, within_days=3)
        db.commit()
        return result
    except SoftTimeLimitExceeded:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(
    base=BaseTask,
    name="workers.tasks.notify_new_opportunity",
    bind=True,
    queue="notifications",
    max_retries=2,
    default_retry_delay=30,
)
def notify_new_opportunity(self: Task, opportunity_id: int) -> dict:
    """Notifies users whose profile matches a newly published opportunity."""
    db, cache = _get_db_and_cache()
    try:
        from workers.worker_app.job_runner import run_new_opportunity_notifier
        result = run_new_opportunity_notifier(opportunity_id, db, cache)
        db.commit()
        return result
    except SoftTimeLimitExceeded:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(
    base=BaseTask,
    name="workers.tasks.notify_new_recommendation",
    bind=True,
    queue="notifications",
    max_retries=2,
    default_retry_delay=30,
)
def notify_new_recommendation(
    self: Task, user_id: int, recommendation_id: int
) -> dict:
    db, cache = _get_db_and_cache()
    try:
        from workers.worker_app.job_runner import run_recommendation_notifier
        result = run_recommendation_notifier(user_id, recommendation_id, db, cache)
        db.commit()
        return result
    except SoftTimeLimitExceeded:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise self.retry(exc=exc)
    finally:
        db.close()


# =============================================================================
# Maintenance tasks
# =============================================================================

@celery_app.task(
    base=BaseTask,
    name="workers.tasks.expire_past_deadline_opportunities",
    bind=True,
    queue="default",
    max_retries=2,
    default_retry_delay=60,
)
def expire_past_deadline_opportunities(self: Task) -> dict:
    from sqlalchemy import and_, update
    from core.enums import OpportunityStatus
    from models.opportunity import Opportunity

    db, _ = _get_db_and_cache()
    try:
        now = datetime.now(UTC)
        result = db.execute(
            update(Opportunity)
            .where(
                and_(
                    Opportunity.status == OpportunityStatus.ACTIVE,
                    Opportunity.deadline < now,
                    Opportunity.deadline.is_not(None),
                )
            )
            .values(status=OpportunityStatus.EXPIRED, updated_at=now)
        )
        expired_count = result.rowcount
        db.commit()
        logger.info("Expired %d opportunities", expired_count)
        return {"expired": expired_count}
    except Exception as exc:
        db.rollback()
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(
    base=BaseTask,
    name="workers.tasks.cleanup_archived_notifications",
    bind=True,
    queue="default",
    max_retries=1,
    default_retry_delay=120,
)
def cleanup_archived_notifications(self: Task) -> dict:
    """Purges archived notifications older than 30 days."""
    from sqlalchemy import and_, delete
    from core.enums import NotificationStatus
    from models.notification import Notification

    db, _ = _get_db_and_cache()
    try:
        cutoff = datetime.now(UTC) - timedelta(days=30)
        result = db.execute(
            delete(Notification).where(
                and_(
                    Notification.status == NotificationStatus.ARCHIVED,
                    Notification.created_at < cutoff,
                )
            )
        )
        deleted = result.rowcount
        db.commit()
        logger.info("Cleaned up %d archived notifications", deleted)
        return {"deleted": deleted}
    except Exception as exc:
        db.rollback()
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(
    base=BaseTask,
    name="workers.tasks.persist_faiss_index",
    bind=True,
    queue="ml",
    max_retries=2,
    default_retry_delay=60,
)
def persist_faiss_index(self: Task) -> dict:
    """Serializes the in-memory FAISS index to disk for crash recovery."""
    try:
        from workers.worker_app.job_runner import save_faiss_index
        return save_faiss_index()
    except Exception as exc:
        raise self.retry(exc=exc)