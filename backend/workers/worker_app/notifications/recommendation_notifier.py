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


def notify_new_recommendation(
    user_id: int,
    recommendation_id: int,
    db: "Session",
    cache: "Redis",
) -> dict:
    from sqlalchemy import select
    from backend.models.recommendation import Recommendation

    rec = db.execute(
        select(Recommendation).where(Recommendation.id == recommendation_id)
    ).scalar_one_or_none()

    if rec is None:
        logger.warning("notify_new_recommendation: rec %d not found", recommendation_id)
        return {"error": "not_found", "recommendation_id": recommendation_id}

    if notification_exists(db, user_id, rec.opportunity_id, NotificationType.NEW_RECOMMENDATION):
        return {"skipped": True, "reason": "already_notified"}

    notif = Notification(
        user_id=user_id,
        opportunity_id=rec.opportunity_id,
        type=NotificationType.NEW_RECOMMENDATION,
        title="New recommendation for you",
        body=(
            f"We found an opportunity matching your profile "
            f"with a relevance score of {rec.score:.0%}."
        ),
        payload={
            "recommendation_id": recommendation_id,
            "opportunity_id": rec.opportunity_id,
            "score": rec.score,
        },
        status=NotificationStatus.UNREAD,
    )
    db.add(notif)
    db.flush()

    logger.info(
        "Recommendation notification created: user=%d rec=%d",
        user_id, recommendation_id,
    )
    return {"notification_created": True, "recommendation_id": recommendation_id}