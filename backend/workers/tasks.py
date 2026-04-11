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

from backend.queue.celery_app import celery_app
from backend.core.config import get_settings

from sqlalchemy import and_, update, delete
from backend.db.session import get_sync_db
from backend.queue.redis_client import get_sync_redis

from backend.workers.worker_app.coordinator import (
    run_scraper_agent,
    run_classifier_agent,
    embed_opportunity,
    run_cluster_agent,
    run_recommendation_agent,
    run_deadline_reminder_agent,
    run_new_opportunity_notifier,
    run_recommendation_notifier,
    save_faiss_index
)

from backend.core.enums import OpportunityStatus, NotificationStatus
from backend.models.opportunity import Opportunity
from backend.models.notification import Notification

logger = logging.getLogger(__name__)
settings = get_settings()

class BaseTask(Task):
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

def _get_db_and_cache():
    return get_sync_db(), get_sync_redis()

@celery_app.task(
    base=BaseTask,
    name="workers.tasks.run_internship_scraper",
    bind=True,
    queue=settings.CELERY_QUEUE_SCRAPING,
    max_retries=settings.CELERY_TASK_MAX_RETRIES_SCRAPING,
    default_retry_delay=settings.CELERY_TASK_RETRY_DELAY_SCRAPING,
)
def run_internship_scraper(self: Task) -> dict:
    db, cache = _get_db_and_cache()
    try:
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
    queue=settings.CELERY_QUEUE_SCRAPING,
    max_retries=settings.CELERY_TASK_MAX_RETRIES_SCRAPING,
    default_retry_delay=settings.CELERY_TASK_RETRY_DELAY_SCRAPING,
)
def run_scholarship_scraper(self: Task) -> dict:
    db, cache = _get_db_and_cache()
    try:
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
    queue=settings.CELERY_QUEUE_SCRAPING,
    max_retries=settings.CELERY_TASK_MAX_RETRIES_SCRAPING,
    default_retry_delay=settings.CELERY_TASK_RETRY_DELAY_SCRAPING,
)
def run_project_scraper(self: Task) -> dict:
    db, cache = _get_db_and_cache()
    try:
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
    queue=settings.CELERY_QUEUE_SCRAPING,
    max_retries=settings.CELERY_TASK_MAX_RETRIES_SCRAPING,
    default_retry_delay=settings.CELERY_TASK_RETRY_DELAY_SCRAPING,
)
def run_certification_scraper(self: Task) -> dict:
    db, cache = _get_db_and_cache()
    try:
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
    queue=settings.CELERY_QUEUE_SCRAPING,
    max_retries=settings.CELERY_TASK_MAX_RETRIES_SCRAPING,
    default_retry_delay=settings.CELERY_TASK_RETRY_DELAY_SCRAPING,
)
def run_postdoc_scraper(self: Task) -> dict:
    db, cache = _get_db_and_cache()
    try:
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

@celery_app.task(
    base=BaseTask,
    name="workers.tasks.run_classifier",
    bind=True,
    queue=settings.CELERY_QUEUE_ML,
    max_retries=settings.CELERY_TASK_MAX_RETRIES_ML,
    default_retry_delay=settings.CELERY_TASK_RETRY_DELAY_ML_CLASSIFIER,
)
def run_classifier(self: Task) -> dict:
    db, cache = _get_db_and_cache()
    try:
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
    queue=settings.CELERY_QUEUE_ML,
    max_retries=settings.CELERY_TASK_MAX_RETRIES_ML,
    default_retry_delay=settings.CELERY_TASK_RETRY_DELAY_ML_FAST,
)
def embed_single_opportunity(self: Task, opportunity_id: int) -> dict:
    db, cache = _get_db_and_cache()
    try:
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
    queue=settings.CELERY_QUEUE_ML,
    max_retries=settings.CELERY_TASK_MAX_RETRIES_ML_HEAVY,
    default_retry_delay=settings.CELERY_TASK_RETRY_DELAY_ML_HEAVY,
)
def run_cluster_recompute(self: Task) -> dict:
    db, cache = _get_db_and_cache()
    try:
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
    queue=settings.CELERY_QUEUE_ML,
    max_retries=settings.CELERY_TASK_MAX_RETRIES_ML_HEAVY,
    default_retry_delay=settings.CELERY_TASK_RETRY_DELAY_ML_CLASSIFIER,
)
def run_recommendation_recompute(self: Task, user_id: int | None = None) -> dict:
    db, cache = _get_db_and_cache()
    try:
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

@celery_app.task(
    base=BaseTask,
    name="workers.tasks.send_deadline_reminders",
    bind=True,
    queue=settings.CELERY_QUEUE_NOTIFICATIONS,
    max_retries=settings.CELERY_TASK_MAX_RETRIES_NOTIFICATIONS,
    default_retry_delay=settings.CELERY_TASK_RETRY_DELAY_NOTIFICATIONS,
)
def send_deadline_reminders(self: Task) -> dict:
    db, cache = _get_db_and_cache()
    try:
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
    queue=settings.CELERY_QUEUE_NOTIFICATIONS,
    max_retries=settings.CELERY_TASK_MAX_RETRIES_NOTIFICATIONS,
    default_retry_delay=settings.CELERY_TASK_RETRY_DELAY_NOTIFICATIONS_FAST,
)
def notify_new_opportunity(self: Task, opportunity_id: int) -> dict:
    db, cache = _get_db_and_cache()
    try:
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
    queue=settings.CELERY_QUEUE_NOTIFICATIONS,
    max_retries=settings.CELERY_TASK_MAX_RETRIES_NOTIFICATIONS,
    default_retry_delay=settings.CELERY_TASK_RETRY_DELAY_NOTIFICATIONS_FAST,
)
def notify_new_recommendation(
    self: Task, user_id: int, recommendation_id: int
) -> dict:
    db, cache = _get_db_and_cache()
    try:
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

@celery_app.task(
    base=BaseTask,
    name="workers.tasks.expire_past_deadline_opportunities",
    bind=True,
    queue=settings.CELERY_QUEUE_DEFAULT,
    max_retries=settings.CELERY_TASK_MAX_RETRIES_DEFAULT,
    default_retry_delay=settings.CELERY_TASK_RETRY_DELAY_DEFAULT,
)
def expire_past_deadline_opportunities(self: Task) -> dict:
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
    queue=settings.CELERY_QUEUE_DEFAULT,
    max_retries=settings.CELERY_TASK_MAX_RETRIES_CLEANUP,
    default_retry_delay=settings.CELERY_TASK_RETRY_DELAY_CLEANUP,
)
def cleanup_archived_notifications(self: Task) -> dict:
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
    queue=settings.CELERY_QUEUE_ML,
    max_retries=settings.CELERY_TASK_MAX_RETRIES_ML,
    default_retry_delay=settings.CELERY_TASK_RETRY_DELAY_DEFAULT,
)
def persist_faiss_index(self: Task) -> dict:
    try:
        return save_faiss_index()
    except Exception as exc:
        raise self.retry(exc=exc)
