import logging
from typing import TYPE_CHECKING
from sqlalchemy import select
from backend.models.notification import Notification
from backend.models.opportunity import Opportunity
from backend.models.user import User
from backend.core.enums import NotificationStatus, NotificationType

if TYPE_CHECKING:
    from redis import Redis
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class OpportunityNotifier:
    def __init__(self, db: Session, cache: Redis):
        self.db = db
        self.cache = cache

    def run(self, opportunity_id: int) -> dict:
        opp = self.db.execute(
            select(Opportunity).where(Opportunity.id == opportunity_id)
        ).scalar_one_or_none()

        if opp is None:
            return {"error": f"Opportunity {opportunity_id} not found"}

        opp_skills = set(s.lower() for s in (opp.required_skills or []))
        opp_tags = set(t.lower() for t in (opp.tags or []))
        opp_domain = opp.domain.value if hasattr(opp.domain, "value") else str(opp.domain)

        users = self.db.execute(select(User).where(User.is_active.is_(True))).scalars().all()

        created = 0
        for user in users:
            user_skills = set(s.lower() for s in (user.skills or []))
            user_interests = set(i.lower() for i in (user.interests or []))

            skill_overlap = bool(user_skills & opp_skills)
            interest_match = opp_domain in user_interests or bool(user_interests & opp_tags)

            if not (skill_overlap or interest_match):
                continue

            already_sent = self.db.execute(
                select(Notification.id).where(
                    Notification.user_id == user.id,
                    Notification.opportunity_id == opp.id,
                    Notification.type == NotificationType.NEW_OPPORTUNITY,
                )
            ).scalar_one_or_none()

            if already_sent:
                continue

            notification = Notification(
                user_id=user.id,
                opportunity_id=opp.id,
                type=NotificationType.NEW_OPPORTUNITY,
                title=f"New opportunity: {opp.title[:80]}",
                body=f"A new {opp.type.value} matching your profile was just published.",
                payload={"opportunity_id": opp.id, "type": opp.type.value},
                status=NotificationStatus.UNREAD,
            )
            self.db.add(notification)
            created += 1

        self.db.flush()
        logger.info(f"New opportunity notifier: opportunity={opportunity_id}, notifications={created}")
        return {"opportunity_id": opportunity_id, "notifications_created": created}
