from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from redis import Redis
    from sqlalchemy.orm import Session

from backend.core.enums import NotificationStatus, NotificationType
from backend.models.notification import Notification
from backend.workers.worker_app.utils import notification_exists

logger = logging.getLogger(__name__)


def notify_new_opportunity(
    opportunity_id: int,
    db: "Session",
    cache: "Redis",
) -> dict:
    from sqlalchemy import select
    from backend.models.opportunity import Opportunity
    from backend.models.user import User

    opp = db.execute(
        select(Opportunity).where(Opportunity.id == opportunity_id)
    ).scalar_one_or_none()

    if opp is None:
        logger.warning("notify_new_opportunity: opportunity %d not found", opportunity_id)
        return {"error": "not_found", "opportunity_id": opportunity_id}

    opp_skills = {s.lower() for s in (opp.required_skills or [])}
    opp_tags = {t.lower() for t in (opp.tags or [])}
    opp_domain = opp.domain.value if hasattr(opp.domain, "value") else str(opp.domain)

    users = db.execute(
        select(User).where(User.is_active.is_(True))
    ).scalars().all()

    created = 0

    for user in users:
        user_skills = {s.lower() for s in (user.skills or [])}
        user_interests = {i.lower() for i in (user.interests or [])}

        skill_match = bool(user_skills & opp_skills)
        interest_match = opp_domain in user_interests or bool(user_interests & opp_tags)

        if not skill_match and not interest_match:
            continue

        if notification_exists(db, user.id, opp.id, NotificationType.NEW_OPPORTUNITY):
            continue

        notif = Notification(
            user_id=user.id,
            opportunity_id=opp.id,
            type=NotificationType.NEW_OPPORTUNITY,
            title=f"New opportunity: {opp.title[:80]}",
            body=f"A new {opp.type.value} matching your profile was just published.",
            payload={"opportunity_id": opp.id, "type": opp.type.value},
            status=NotificationStatus.UNREAD,
        )
        db.add(notif)
        created += 1

    db.flush()
    logger.info(
        "New opportunity notifications: opportunity=%d created=%d",
        opportunity_id, created,
    )
    return {"opportunity_id": opportunity_id, "notifications_created": created}