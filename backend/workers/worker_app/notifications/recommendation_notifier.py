import logging
from typing import TYPE_CHECKING
from sqlalchemy import select
from backend.models.notification import Notification
from backend.models.recommendation import Recommendation
from backend.core.enums import NotificationStatus, NotificationType

if TYPE_CHECKING:
    from redis import Redis
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class RecommendationNotifier:
    def __init__(self, db: Session, cache: Redis):
        self.db = db
        self.cache = cache

    def run(self, user_id: int, recommendation_id: int) -> dict:
        rec = self.db.execute(
            select(Recommendation).where(Recommendation.id == recommendation_id)
        ).scalar_one_or_none()

        if rec is None:
            return {"error": f"Recommendation {recommendation_id} not found"}

        notification = Notification(
            user_id=user_id,
            opportunity_id=rec.opportunity_id,
            type=NotificationType.NEW_RECOMMENDATION,
            title="New recommendation for you",
            body=f"We found an opportunity matching your profile with a relevance score of {rec.score:.0%}.",
            payload={
                "recommendation_id": recommendation_id,
                "opportunity_id": rec.opportunity_id,
                "score": rec.score,
            },
            status=NotificationStatus.UNREAD,
        )
        self.db.add(notification)
        self.db.flush()
        return {"notification_created": True, "recommendation_id": recommendation_id}
