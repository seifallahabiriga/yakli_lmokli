from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from backend.workers.worker_app.agents.base_agent import ObservatoryAgent
from backend.workers.worker_app.ml import clusterer, faiss_store, tagger
from backend.workers.worker_app.utils import centroid_version_hash, dominant_domains

if TYPE_CHECKING:
    from backend.workers.worker_app.agents.coordinator_agent import ObservatoryModel


class ClusterAgent(ObservatoryAgent):

    def __init__(self, model: "ObservatoryModel", db, cache) -> None:
        super().__init__(model, db, cache)

    def step(self) -> None:
        report = clusterer.drift_check(self.db)
        self.logger.info(
            "ClusterAgent drift: %s (recluster=%s)",
            report.reason, report.needs_recluster,
        )

        if report.reason in ("no_embeddings", "insufficient_data"):
            self.last_result = {"action": "skip", "reason": report.reason}
            return

        if report.needs_recluster:
            self.last_result = self._full_recluster()
        else:
            self.last_result = self._incremental_assign()

    # ------------------------------------------------------------------

    def _full_recluster(self) -> dict:
        from sqlalchemy import delete, update
        from backend.models.cluster import OpportunityCluster
        from backend.models.opportunity import Opportunity

        self.logger.info("ClusterAgent: full re-cluster starting")

        try:
            embeddings, opp_ids = clusterer.load_all_embeddings(self.db)
        except ValueError as exc:
            self.logger.warning("ClusterAgent: %s", exc)
            return {"action": "skip", "reason": str(exc)}

        result = clusterer.fit(embeddings)

        # Wipe old clusters — FK SET NULL handles opportunity.cluster_id
        self.db.execute(delete(OpportunityCluster))
        self.db.flush()

        now = datetime.now(UTC)
        new_clusters: list[OpportunityCluster] = []

        for idx in range(result.k):
            mask = result.labels == idx
            member_opps = [
                self.db.get(Opportunity, opp_ids[i])
                for i in range(len(opp_ids)) if mask[i]
            ]
            member_opps = [o for o in member_opps if o is not None]
            centroid = result.centroids[idx].tolist()

            cluster = OpportunityCluster(
                name=f"Cluster {idx + 1}",
                centroid=centroid,
                top_keywords=tagger.extract_keywords_from_texts(
                    [f"{o.title} {' '.join(o.tags or [])}" for o in member_opps]
                ),
                dominant_domains=dominant_domains(member_opps),
                member_count=int(mask.sum()),
                faiss_index_id=idx,
                centroid_version=centroid_version_hash(centroid),
                algorithm_meta={
                    "algorithm": "kmeans",
                    "k": result.k,
                    "inertia": round(result.inertia, 4),
                    "n_samples": result.n_samples,
                    "recomputed_at": now.isoformat(),
                },
            )
            self.db.add(cluster)
            new_clusters.append(cluster)

        self.db.flush()

        # Assign opportunities
        for i, opp_id in enumerate(opp_ids):
            opp = self.db.get(Opportunity, opp_id)
            if opp is None:
                continue
            cluster = new_clusters[result.labels[i]]
            opp.cluster_id = cluster.id
            opp.needs_cluster_assignment = False

        self.db.flush()

        # Rebuild FAISS index
        faiss_store.build_index(
            centroids=result.centroids,
            faiss_ids=[c.faiss_index_id for c in new_clusters],
            cluster_db_ids=[c.id for c in new_clusters],
        )

        self._update_member_counts(new_clusters)
        self._invalidate_cache()

        self.logger.info(
            "ClusterAgent full re-cluster done — k=%d, n=%d",
            result.k, result.n_samples,
        )
        return {
            "action": "full_recluster",
            "clusters": result.k,
            "opportunities": result.n_samples,
            "inertia": round(result.inertia, 4),
        }

    def _incremental_assign(self) -> dict:
        from backend.models.opportunity import Opportunity

        embeddings, opp_ids = clusterer.load_unassigned_embeddings(self.db)

        if len(opp_ids) == 0:
            return {"action": "incremental", "assigned": 0}

        cluster_ids = faiss_store.search_nearest_batch(embeddings)
        assigned = 0

        for opp_id, cluster_db_id in zip(opp_ids, cluster_ids):
            opp = self.db.get(Opportunity, opp_id)
            if opp is None or cluster_db_id is None:
                continue
            opp.cluster_id = cluster_db_id
            opp.needs_cluster_assignment = False
            assigned += 1

        self.db.flush()
        self._invalidate_cache()

        self.logger.info("ClusterAgent incremental: assigned %d", assigned)
        return {"action": "incremental", "assigned": assigned}

    def _update_member_counts(self, clusters) -> None:
        from sqlalchemy import func, select, update
        from backend.models.cluster import OpportunityCluster
        from backend.models.opportunity import Opportunity

        counts = self.db.execute(
            select(Opportunity.cluster_id, func.count().label("cnt"))
            .where(Opportunity.cluster_id.is_not(None))
            .group_by(Opportunity.cluster_id)
        ).all()

        for row in counts:
            self.db.execute(
                update(OpportunityCluster)
                .where(OpportunityCluster.id == row.cluster_id)
                .values(member_count=row.cnt)
            )
        self.db.flush()

    def _invalidate_cache(self) -> None:
        keys = self.cache.keys("clusters:*")
        if keys:
            self.cache.delete(*keys)