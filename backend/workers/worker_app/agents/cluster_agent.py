import logging
from sqlalchemy import func, select
from backend.models.opportunity import Opportunity
from backend.workers.worker_app.agents.base_agent import BaseAgent
from backend.workers.worker_app.ml.faiss_store import get_faiss_index
from backend.workers.worker_app.ml.clusterer import full_recluster, incremental_cluster_assign, update_cluster_stats, invalidate_cluster_cache
import numpy as np

logger = logging.getLogger(__name__)
DRIFT_THRESHOLD = 0.10

class ClusterAgent(BaseAgent):
    def run(self) -> dict:
        total_embedded = self.db.execute(
            select(func.count()).select_from(Opportunity).where(
                Opportunity.embedding.is_not(None)
            )
        ).scalar_one()

        total_unassigned = self.db.execute(
            select(func.count()).select_from(Opportunity).where(
                Opportunity.needs_cluster_assignment.is_(True)
            )
        ).scalar_one()

        if total_embedded == 0:
            logger.info("Cluster agent: no embedded opportunities yet")
            return {"action": "skip", "reason": "no_embeddings"}

        drift_ratio = total_unassigned / total_embedded
        logger.info(
            f"Cluster agent: {total_unassigned} unassigned / {total_embedded} total (drift={drift_ratio * 100:.2f}%)"
        )

        faiss_idx = get_faiss_index()

        if faiss_idx is None or drift_ratio > DRIFT_THRESHOLD:
            return full_recluster(self.db, self.cache)
        else:
            unassigned_opps = self.db.execute(
                select(Opportunity).where(
                    Opportunity.needs_cluster_assignment.is_(True)
                )
            ).scalars().all()

            embeddings = np.array(
                [opp.embedding for opp in unassigned_opps], dtype=np.float32
            )
            assigned = incremental_cluster_assign(unassigned_opps, embeddings, self.db)
            update_cluster_stats(self.db)
            invalidate_cluster_cache(self.cache)
            return {"action": "incremental", "assigned": assigned}
