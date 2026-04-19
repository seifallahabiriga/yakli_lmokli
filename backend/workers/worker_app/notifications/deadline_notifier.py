from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

from backend.core.enums import NotificationStatus, NotificationType, OpportunityStatus, RecommendationStatus
from backend.models.notification import Notification
from backend.workers.worker_app.utils import notification_exists

logger = logging.getLogger(__name__)


def send_deadline_reminders(db: "Session", within_days: int = 3) -> dict:
    from sqlalchemy import and_, select
    from backend.models.opportunity import Opportunity
    from backend.models.recommendation import Recommendation

    now = datetime.now(UTC)
    cutoff = now + timedelta(days=within_days)

    expiring = db.execute(
        select(Opportunity).where(
            and_(
                Opportunity.status == OpportunityStatus.ACTIVE,
                Opportunity.deadline >= now,
                Opportunity.deadline <= cutoff,
            )
        )
    ).scalars().all()

    created = 0

    for opp in expiring:
        recs = db.execute(
            select(Recommendation).where(
                and_(
                    Recommendation.opportunity_id == opp.id,
                    Recommendation.status == RecommendationStatus.SCORED,
                )
            )
        ).scalars().all()

        for rec in recs:
            if notification_exists(db, rec.user_id, opp.id, NotificationType.DEADLINE_REMINDER):
                continue

            days_left = (opp.deadline - now).days
            notif = Notification(
                user_id=rec.user_id,
                opportunity_id=opp.id,
                type=NotificationType.DEADLINE_REMINDER,
                title=f"Deadline in {days_left} day{'s' if days_left != 1 else ''}: {opp.title[:80]}",
                body=f"Application deadline for '{opp.title}' is approaching.",
                payload={
                    "opportunity_id": opp.id,
                    "days_left": days_left,
                    "deadline": opp.deadline.isoformat() if opp.deadline else None,
                },
                status=NotificationStatus.UNREAD,
            )
            db.add(notif)
            created += 1

    db.flush()
    logger.info("Deadline reminders created: %d", created)
    return {"notifications_created": created}