from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from redis import Redis
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# =============================================================================
# ML pipeline — Mesa-backed
# =============================================================================

def run_classifier_agent(db: "Session", cache: "Redis") -> dict:
    from backend.workers.worker_app.agents.coordinator_agent import ObservatoryModel
    model = ObservatoryModel(db, cache, mode="classify")
    model.step()
    return model.result


def run_cluster_agent(db: "Session", cache: "Redis") -> dict:
    from backend.workers.worker_app.agents.coordinator_agent import ObservatoryModel
    model = ObservatoryModel(db, cache, mode="cluster")
    model.step()
    return model.result


def run_recommendation_agent(
    db: "Session",
    cache: "Redis",
    user_id: int | None = None,
) -> dict:
    from backend.workers.worker_app.agents.coordinator_agent import ObservatoryModel
    model = ObservatoryModel(db, cache, mode="recommend", user_id=user_id)
    model.step()
    return model.result


def embed_opportunity(opportunity_id: int, db: "Session") -> dict:
    """
    Embeds a single opportunity immediately after scraping.
    Called by the embed_single_opportunity Celery task (producer trigger).
    Reuses ClassifierAgent logic but scoped to one row.
    """
    from sqlalchemy import select
    from datetime import UTC, datetime
    from backend.core.enums import OpportunityStatus
    from backend.models.opportunity import Opportunity
    from backend.workers.worker_app.ml import embedder, faiss_store, tagger
    from backend.workers.worker_app.utils import build_embedding_text

    opp = db.execute(
        select(Opportunity).where(Opportunity.id == opportunity_id)
    ).scalar_one_or_none()

    if opp is None:
        logger.warning("embed_opportunity: opportunity %d not found", opportunity_id)
        return {"error": "not_found", "opportunity_id": opportunity_id}

    vec = embedder.encode_one(build_embedding_text(opp))
    opp.embedding = vec.tolist()
    opp.classified_at = datetime.now(UTC)
    opp.needs_cluster_assignment = True
    opp.status = OpportunityStatus.ACTIVE
    opp.tags = tagger.enrich_opportunity_tags(opp)

    cluster_db_id = faiss_store.search_nearest(vec)
    if cluster_db_id is not None:
        opp.cluster_id = cluster_db_id
        opp.needs_cluster_assignment = False

    db.flush()
    logger.info("embed_opportunity: opportunity %d embedded", opportunity_id)
    return {"opportunity_id": opportunity_id, "embedded": True}


# =============================================================================
# Scraper dispatch — no Mesa needed
# =============================================================================

def run_scraper_agent(
    agent_type: str,
    db: "Session",
    cache: "Redis",
) -> dict:
    from sqlalchemy import select
    from backend.models.opportunity import Opportunity

    scraper = _get_scraper(agent_type)
    if scraper is None:
        return {"error": f"unknown_agent_type: {agent_type}"}

    logger.info("Scraper starting: %s", agent_type)
    raw_items = scraper.run()
    logger.info("Scraper %s collected %d raw items", agent_type, len(raw_items))

    inserted = 0
    skipped = 0

    for item in raw_items:
        url = item.get("url", "").strip()
        if not url:
            skipped += 1
            continue

        exists = db.execute(
            select(Opportunity.id).where(Opportunity.url == url)
        ).scalar_one_or_none()

        if exists is not None:
            skipped += 1
            continue

        from backend.models.opportunity import Opportunity as OppModel
        opp = OppModel(
            title=item.get("title", "Untitled")[:512],
            description=item.get("description"),
            organization=item.get("organization"),
            source=item.get("source", agent_type),
            url=url,
            type=item.get("type"),
            domain=item.get("domain", "other"),
            level=item.get("level", "all"),
            location_type=item.get("location_type", "unknown"),
            location=item.get("location"),
            country=item.get("country"),
            eligibility=item.get("eligibility", {}),
            required_skills=item.get("required_skills", []),
            tags=item.get("tags", []),
            deadline=item.get("deadline"),
            start_date=item.get("start_date"),
            duration_months=item.get("duration_months"),
            is_paid=item.get("is_paid"),
            stipend_amount=item.get("stipend_amount"),
            stipend_currency=item.get("stipend_currency"),
            scraper_type=item.get("scraper_type", "dynamic"),
            raw_data=item,
        )
        db.add(opp)
        inserted += 1

    db.flush()
    logger.info("Scraper %s done — inserted: %d, skipped: %d", agent_type, inserted, skipped)
    return {"agent": agent_type, "inserted": inserted, "skipped": skipped}


def _get_scraper(agent_type: str):
    from backend.workers.worker_app.scrapers.internship_scraper import InternshipScraper
    from backend.workers.worker_app.scrapers.scholarship_scraper import ScholarshipScraper
    from backend.workers.worker_app.scrapers.project_scraper import ProjectScraper
    from backend.workers.worker_app.scrapers.certification_scraper import CertificationScraper
    from backend.workers.worker_app.scrapers.postdoc_scraper import PostdocScraper

    return {
        "internship":   InternshipScraper(),
        "scholarship":  ScholarshipScraper(),
        "project":      ProjectScraper(),
        "certification": CertificationScraper(),
        "postdoc":      PostdocScraper(),
    }.get(agent_type)


# =============================================================================
# Notification dispatch — no Mesa needed
# =============================================================================

def run_deadline_reminder_agent(
    db: "Session",
    cache: "Redis",
    within_days: int = 3,
) -> dict:
    from backend.workers.worker_app.notifications.deadline_notifier import send_deadline_reminders
    return send_deadline_reminders(db, within_days=within_days)


def run_new_opportunity_notifier(
    opportunity_id: int,
    db: "Session",
    cache: "Redis",
) -> dict:
    from backend.workers.worker_app.notifications.opportunity_notifier import notify_new_opportunity
    return notify_new_opportunity(opportunity_id, db, cache)


def run_recommendation_notifier(
    user_id: int,
    recommendation_id: int,
    db: "Session",
    cache: "Redis",
) -> dict:
    from backend.workers.worker_app.notifications.recommendation_notifier import notify_new_recommendation
    return notify_new_recommendation(user_id, recommendation_id, db, cache)


# =============================================================================
# FAISS persistence
# =============================================================================

def save_faiss_index() -> dict:
    from backend.workers.worker_app.ml.faiss_store import save_index
    return save_index()