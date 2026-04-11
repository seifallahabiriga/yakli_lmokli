from celery import Celery
from celery.schedules import crontab

from backend.core.config import get_settings

settings = get_settings()

# =============================================================================
# Celery application
# =============================================================================

celery_app = Celery(
    "observatory",
    broker=settings.REDIS_BROKER_URL,
    backend=settings.REDIS_BACKEND_URL,
    include=[
        "workers.tasks",  # all task definitions live here
    ],
)

# =============================================================================
# Configuration
# =============================================================================

celery_app.conf.update(
    # Serialization
    task_serializer=settings.CELERY_TASK_SERIALIZER,
    result_serializer=settings.CELERY_RESULT_SERIALIZER,
    accept_content=settings.CELERY_ACCEPT_CONTENT,

    # Timezone
    timezone=settings.CELERY_TIMEZONE,
    enable_utc=settings.CELERY_ENABLE_UTC,

    # Task behaviour
    task_track_started=settings.CELERY_TASK_TRACK_STARTED,
    task_time_limit=settings.CELERY_TASK_TIME_LIMIT,
    task_soft_time_limit=settings.CELERY_TASK_SOFT_TIME_LIMIT,

    # Result expiry — keep results for 24h then discard
    result_expires=60 * 60 * 24,

    # Retry policy defaults (individual tasks can override)
    task_max_retries=settings.SCRAPER_MAX_RETRIES,
    task_default_retry_delay=30,  # seconds

    # Worker concurrency — tune per machine; 4 is safe for local dev
    worker_concurrency=4,
    worker_prefetch_multiplier=1,   # one task at a time per worker process

    # Prevent tasks from being silently lost on worker crash
    task_acks_late=True,
    task_reject_on_worker_lost=True,

    # Routing — all tasks go to the default queue unless overridden
    task_default_queue="default",
    task_queues={
        "default": {},
        "scraping": {},     # observer agents
        "ml": {},           # classifier, cluster, recommendation
        "notifications": {} # notification agent
    },
)

# =============================================================================
# Beat schedule — periodic tasks
# =============================================================================

celery_app.conf.beat_schedule = {
    # --- Observer agents ---
    "scrape-internships": {
        "task": "workers.tasks.run_internship_scraper",
        "schedule": settings.SCRAPE_INTERVAL_INTERNSHIPS,
        "options": {"queue": "scraping"},
    },
    "scrape-scholarships": {
        "task": "workers.tasks.run_scholarship_scraper",
        "schedule": settings.SCRAPE_INTERVAL_SCHOLARSHIPS,
        "options": {"queue": "scraping"},
    },
    "scrape-projects": {
        "task": "workers.tasks.run_project_scraper",
        "schedule": settings.SCRAPE_INTERVAL_PROJECTS,
        "options": {"queue": "scraping"},
    },
    "scrape-certifications": {
        "task": "workers.tasks.run_certification_scraper",
        "schedule": settings.SCRAPE_INTERVAL_CERTS,
        "options": {"queue": "scraping"},
    },
    "scrape-postdocs": {
        "task": "workers.tasks.run_postdoc_scraper",
        "schedule": settings.SCRAPE_INTERVAL_SCHOLARSHIPS,  # same cadence as scholarships
        "options": {"queue": "scraping"},
    },

    # --- Analysis agents ---
    "classify-new-opportunities": {
        "task": "workers.tasks.run_classifier",
        "schedule": 60 * 15,  # every 15 min — picks up newly scraped drafts faster
        "options": {"queue": "ml"},
    },
    "recompute-clusters": {
        "task": "workers.tasks.run_cluster_recompute",
        "schedule": settings.CLUSTER_RECOMPUTE_INTERVAL,
        "options": {"queue": "ml"},
    },
    "recompute-recommendations": {
        "task": "workers.tasks.run_recommendation_recompute",
        "schedule": settings.RECOMMENDATION_RECOMPUTE_INTERVAL,
        "options": {"queue": "ml"},
    },
    "persist-faiss-index": {
        "task": "workers.tasks.persist_faiss_index",
        "schedule": 60 * 60,  # every 1h — saves in-memory index to disk
        "options": {"queue": "ml"},
    },

    # --- Maintenance ---
    "expire-past-deadlines": {
        "task": "workers.tasks.expire_past_deadline_opportunities",
        "schedule": crontab(hour="*/6"),  # every 6 hours
        "options": {"queue": "default"},
    },
    "send-deadline-reminders": {
        "task": "workers.tasks.send_deadline_reminders",
        "schedule": crontab(hour="8", minute="0"),  # daily at 08:00 UTC
        "options": {"queue": "notifications"},
    },
    "cleanup-archived-notifications": {
        "task": "workers.tasks.cleanup_archived_notifications",
        "schedule": crontab(hour="2", minute="0"),  # daily at 02:00 UTC
        "options": {"queue": "default"},
    },
}