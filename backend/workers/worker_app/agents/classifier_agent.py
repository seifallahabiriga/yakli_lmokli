from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from backend.core.enums import OpportunityStatus
from backend.workers.worker_app.agents.base_agent import ObservatoryAgent
from backend.workers.worker_app.ml import embedder, faiss_store, tagger
from backend.workers.worker_app.utils import build_embedding_text

if TYPE_CHECKING:
    from backend.workers.worker_app.agents.coordinator_agent import ObservatoryModel


class ClassifierAgent(ObservatoryAgent):

    def __init__(self, model: "ObservatoryModel", db, cache) -> None:
        super().__init__(model, db, cache)

    def step(self) -> None:
        from sqlalchemy import select
        from backend.models.opportunity import Opportunity

        rows = self.db.execute(
            select(Opportunity).where(Opportunity.embedding.is_(None))
        ).scalars().all()

        if not rows:
            self.logger.info("ClassifierAgent: no unembedded opportunities")
            self.last_result = {"embedded": 0, "assigned": 0}
            return

        self.logger.info("ClassifierAgent: embedding %d opportunities", len(rows))

        texts = [build_embedding_text(opp) for opp in rows]
        embeddings = embedder.encode(texts)

        now = datetime.now(UTC)
        assigned = 0

        for opp, vec in zip(rows, embeddings):
            opp.embedding = vec.tolist()
            opp.classified_at = now
            opp.needs_cluster_assignment = True
            opp.status = OpportunityStatus.ACTIVE
            opp.tags = tagger.enrich_opportunity_tags(opp)

            cluster_db_id = faiss_store.search_nearest(vec)
            if cluster_db_id is not None:
                opp.cluster_id = cluster_db_id
                opp.needs_cluster_assignment = False
                assigned += 1

        self.db.flush()

        self.logger.info(
            "ClassifierAgent done — embedded: %d, assigned: %d",
            len(rows), assigned,
        )
        self.last_result = {"embedded": len(rows), "assigned": assigned}