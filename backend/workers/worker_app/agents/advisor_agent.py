import logging
from datetime import UTC, datetime
from sqlalchemy import select
from backend.models.user import User
from backend.models.opportunity import Opportunity
from backend.models.recommendation import Recommendation
from backend.core.enums import OpportunityStatus, RecommendationStatus
from backend.workers.worker_app.agents.base_agent import BaseAgent
from backend.workers.worker_app.ml.embedder import get_encoder
from backend.workers.worker_app.ml.scorer import build_user_profile_text, score_opportunity
import numpy as np

logger = logging.getLogger(__name__)

class AdvisorAgent(BaseAgent):
    def run(self, user_id: int | None = None) -> dict:
        user_query = select(User).where(User.is_active.is_(True))
        if user_id is not None:
            user_query = user_query.where(User.id == user_id)
        users = self.db.execute(user_query).scalars().all()

        if not users:
            return {"users_processed": 0, "recommendations_created": 0}

        active_opps = self.db.execute(
            select(Opportunity).where(
                Opportunity.status == OpportunityStatus.ACTIVE,
                Opportunity.embedding.is_not(None),
            )
        ).scalars().all()

        if not active_opps:
            return {"users_processed": len(users), "recommendations_created": 0}

        opp_embeddings = np.array(
            [opp.embedding for opp in active_opps], dtype=np.float32
        )

        encoder = get_encoder()
        total_created = 0
        now = datetime.now(UTC)

        for user in users:
            profile_text = build_user_profile_text(user)
            profile_embedding: np.ndarray = encoder.encode(
                [profile_text], normalize_embeddings=True
            )[0]

            similarities = opp_embeddings @ profile_embedding 

            for i, opp in enumerate(active_opps):
                score, breakdown = score_opportunity(
                    user=user,
                    opp=opp,
                    semantic_sim=float(similarities[i]),
                    now=now,
                )

                if score < 0.2:
                    continue

                existing = self.db.execute(
                    select(Recommendation).where(
                        Recommendation.user_id == user.id,
                        Recommendation.opportunity_id == opp.id,
                    )
                ).scalar_one_or_none()

                if existing is None:
                    rec = Recommendation(
                        user_id=user.id,
                        opportunity_id=opp.id,
                        score=score,
                        score_breakdown=breakdown,
                        status=RecommendationStatus.SCORED,
                        scored_at=now,
                    )
                    self.db.add(rec)
                    total_created += 1
                else:
                    if abs(existing.score - score) > 0.05:
                        existing.score = score
                        existing.score_breakdown = breakdown
                        existing.scored_at = now

            user_recs = self.db.execute(
                select(Recommendation)
                .where(
                    Recommendation.user_id == user.id,
                    Recommendation.status == RecommendationStatus.SCORED,
                )
                .order_by(Recommendation.score.desc())
            ).scalars().all()

            for rank, rec in enumerate(user_recs, start=1):
                rec.rank = rank

            self.cache.delete(f"recommendations:user:{user.id}")

        self.db.flush()
        logger.info(f"Recommendation agent done — users: {len(users)}, created: {total_created}")
        return {"users_processed": len(users), "recommendations_created": total_created}
