from typing import TYPE_CHECKING
from backend.workers.worker_app.agents.coordinator_agent import CoordinatorAgent
from backend.workers.worker_app.agents.classifier_agent import ClassifierAgent
from backend.workers.worker_app.agents.cluster_agent import ClusterAgent
from backend.workers.worker_app.agents.advisor_agent import AdvisorAgent
from backend.workers.worker_app.notifications.deadline_notifier import DeadlineNotifier
from backend.workers.worker_app.notifications.opportunity_notifier import OpportunityNotifier
from backend.workers.worker_app.notifications.recommendation_notifier import RecommendationNotifier
from backend.workers.worker_app.ml.faiss_store import save_faiss_index
from backend.workers.worker_app.ml.embedder import embed_opportunity

if TYPE_CHECKING:
    from redis import Redis
    from sqlalchemy.orm import Session

def run_scraper_agent(agent_type: str, db: 'Session', cache: 'Redis') -> dict:
    return CoordinatorAgent(db, cache).run_scraper(agent_type)

def run_classifier_agent(db: 'Session', cache: 'Redis') -> dict:
    return ClassifierAgent(db, cache).run()

def run_cluster_agent(db: 'Session', cache: 'Redis') -> dict:
    return ClusterAgent(db, cache).run()

def run_recommendation_agent(db: 'Session', cache: 'Redis', user_id: int | None = None) -> dict:
    return AdvisorAgent(db, cache).run(user_id)

def run_deadline_reminder_agent(db: 'Session', cache: 'Redis', within_days: int = 3) -> dict:
    return DeadlineNotifier(db, cache).run(within_days)

def run_new_opportunity_notifier(opportunity_id: int, db: 'Session', cache: 'Redis') -> dict:
    return OpportunityNotifier(db, cache).run(opportunity_id)

def run_recommendation_notifier(user_id: int, recommendation_id: int, db: 'Session', cache: 'Redis') -> dict:
    return RecommendationNotifier(db, cache).run(user_id, recommendation_id)

__all__ = [
    "run_scraper_agent",
    "run_classifier_agent",
    "run_cluster_agent",
    "run_recommendation_agent",
    "run_deadline_reminder_agent",
    "run_new_opportunity_notifier",
    "run_recommendation_notifier",
    "save_faiss_index",
    "embed_opportunity",
]
