import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from sqlalchemy import and_, select
from backend.models.notification import Notification
from backend.models.opportunity import Opportunity
from backend.models.recommendation import Recommendation
from backend.core.enums import (
    NotificationStatus, NotificationType,
    OpportunityStatus, RecommendationStatus,
)

if TYPE_CHECKING:
    from redis import Redis
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class DeadlineNotifier:
    def __init__(self, db: Session, cache: Redis):
        self.db = db
        self.cache = cache

    def run(self, within_days: int = 3) -> dict:
        cutoff = datetime.now(UTC) + timedelta(days=within_days)
        now = datetime.now(UTC)

        expiring = self.db.execute(
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
            recs = self.db.execute(
                select(Recommendation).where(
                    and_(
                        Recommendation.opportunity_id == opp.id,
                        Recommendation.status == RecommendationStatus.SCORED,
                    )
                )
            ).scalars().all()

            for rec in recs:
                already_sent = self.db.execute(
                    select(Notification.id).where(
                        and_(
                            Notification.user_id == rec.user_id,
                            Notification.opportunity_id == opp.id,
                            Notification.type == NotificationType.DEADLINE_REMINDER,
                        )
                    )
                ).scalar_one_or_none()

                if already_sent:
                    continue

                days_left = (opp.deadline - now).days
                notification = Notification(
                    user_id=rec.user_id,
                    opportunity_id=opp.id,
                    type=NotificationType.DEADLINE_REMINDER,
                    title=f"Deadline in {days_left} day{'s' if days_left != 1 else ''}: {opp.title[:80]}",
                    body=f"The application deadline for '{opp.title}' is approaching.",
                    payload={
                        "opportunity_id": opp.id,
                        "days_left": days_left,
                        "deadline": opp.deadline.isoformat() if opp.deadline else None,
                    },
                    status=NotificationStatus.UNREAD,
                )
                self.db.add(notification)
                created += 1

        self.db.flush()
        logger.info(f"Deadline reminder agent: created {created} notifications")
        return {"notifications_created": created}
