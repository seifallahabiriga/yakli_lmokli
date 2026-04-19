from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from backend.core.enums import OpportunityStatus, RecommendationStatus
from backend.models.recommendation import Recommendation
from backend.workers.worker_app.agents.base_agent import ObservatoryAgent
from backend.workers.worker_app.ml import embedder, scorer
from backend.workers.worker_app.utils import build_user_profile_text

if TYPE_CHECKING:
    from backend.workers.worker_app.agents.coordinator_agent import ObservatoryModel

import numpy as np


class AdvisorAgent(ObservatoryAgent):

    def __init__(
        self,
        model: "ObservatoryModel",
        db,
        cache,
        user_id: int | None = None,
    ) -> None:
        super().__init__(model, db, cache)
        self.user_id = user_id

    def step(self) -> None:
        from sqlalchemy import select
        from backend.models.opportunity import Opportunity
        from backend.models.user import User

        user_query = select(User).where(User.is_active.is_(True))
        if self.user_id is not None:
            user_query = user_query.where(User.id == self.user_id)
        users = self.db.execute(user_query).scalars().all()

        if not users:
            self.last_result = {"users_processed": 0, "recommendations_created": 0}
            return

        active_opps = self.db.execute(
            select(Opportunity).where(
                Opportunity.status == OpportunityStatus.ACTIVE,
                Opportunity.embedding.is_not(None),
            )
        ).scalars().all()

        if not active_opps:
            self.last_result = {"users_processed": len(users), "recommendations_created": 0}
            return

        opp_embeddings = np.array(
            [opp.embedding for opp in active_opps], dtype=np.float32
        )

        now = datetime.now(UTC)
        total_created = 0

        for user in users:
            profile_text = build_user_profile_text(user)
            profile_vec = embedder.encode_one(profile_text)

            # cosine similarities via dot product on L2-normalised vectors
            similarities = opp_embeddings @ profile_vec

            new_recs = []
            for i, opp in enumerate(active_opps):
                score_val, breakdown = scorer.score_opportunity(
                    user, opp, float(similarities[i]), now
                )

                if not scorer.is_worth_storing(score_val):
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
                        score=score_val,
                        score_breakdown=breakdown,
                        status=RecommendationStatus.SCORED,
                        scored_at=now,
                    )
                    self.db.add(rec)
                    new_recs.append(rec)
                    total_created += 1
                elif abs(existing.score - score_val) > 0.05:
                    existing.score = score_val
                    existing.score_breakdown = breakdown
                    existing.scored_at = now

            self.db.flush()
            self._rank_user_recommendations(user.id)
            self.cache.delete(f"recommendations:user:{user.id}")

        self.logger.info(
            "AdvisorAgent done — users: %d, created: %d",
            len(users), total_created,
        )
        self.last_result = {
            "users_processed": len(users),
            "recommendations_created": total_created,
        }

    def _rank_user_recommendations(self, user_id: int) -> None:
        from sqlalchemy import select
        from sqlalchemy import update as sa_update
        from backend.models.recommendation import Recommendation

        recs = self.db.execute(
            select(Recommendation)
            .where(
                Recommendation.user_id == user_id,
                Recommendation.status == RecommendationStatus.SCORED,
            )
            .order_by(Recommendation.score.desc())
        ).scalars().all()

        for rank, rec in enumerate(recs, start=1):
            rec.rank = rank

        self.db.flush()