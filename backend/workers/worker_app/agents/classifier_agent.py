from datetime import UTC, datetime
from sqlalchemy import select
from backend.core.enums import OpportunityStatus
from backend.models.opportunity import Opportunity
from backend.workers.worker_app.agents.base_agent import BaseAgent
from backend.workers.worker_app.ml.embedder import get_encoder, build_embedding_text
from backend.workers.worker_app.ml.tagger import extract_tags
from backend.workers.worker_app.ml.clusterer import incremental_cluster_assign
import numpy as np

class ClassifierAgent(BaseAgent):
    def run(self) -> dict:
        import logging
        logger = logging.getLogger(__name__)

        rows = self.db.execute(
            select(Opportunity).where(Opportunity.embedding.is_(None))
        ).scalars().all()

        if not rows:
            logger.info("Classifier: no unembedded opportunities found")
            return {"embedded": 0, "assigned": 0}

        logger.info(f"Classifier: embedding {len(rows)} opportunities")

        encoder = get_encoder()
        texts = [build_embedding_text(opp) for opp in rows]

        embeddings: np.ndarray = encoder.encode(
            texts,
            batch_size=32,
            show_progress_bar=False,
            normalize_embeddings=True,
        )

        now = datetime.now(UTC)

        for opp, embedding in zip(rows, embeddings):
            opp.embedding = embedding.tolist()
            opp.classified_at = now
            opp.needs_cluster_assignment = True
            opp.status = OpportunityStatus.ACTIVE

            extra_tags = extract_tags(opp.title, opp.description or "")
            if extra_tags:
                existing = set(opp.tags or [])
                opp.tags = list(existing | extra_tags)

        self.db.flush()

        assigned = incremental_cluster_assign(rows, embeddings, self.db)

        logger.info(f"Classifier done — embedded: {len(rows)}, cluster-assigned: {assigned}")
        return {"embedded": len(rows), "assigned": assigned}
