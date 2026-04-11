from __future__ import annotations
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING
import numpy as np
from backend.core.config import get_settings
from backend.workers.worker_app.ml.faiss_store import get_faiss_index, faiss_id_to_cluster, centroid_version, invalidate_cluster_cache, set_faiss_state

if TYPE_CHECKING:
    from redis import Redis
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)
settings = get_settings()

def full_recluster(db: Session, cache: Redis) -> dict:
    import faiss
    from sklearn.cluster import KMeans
    from sqlalchemy import delete, select, update
    from backend.models.cluster import OpportunityCluster
    from backend.models.opportunity import Opportunity

    logger.info("Full re-cluster starting")
    rows = db.execute(select(Opportunity).where(Opportunity.embedding.is_not(None))).scalars().all()

    if len(rows) < settings.CLUSTER_N_CLUSTERS:
        logger.warning(f"Not enough opportunities ({len(rows)}) to form {settings.CLUSTER_N_CLUSTERS} clusters — skipping")
        return {"action": "skip", "reason": "insufficient_data", "count": len(rows)}

    embeddings = np.array([row.embedding for row in rows], dtype=np.float32)
    k = min(settings.CLUSTER_N_CLUSTERS, len(rows))
    kmeans = KMeans(n_clusters=k, random_state=42, n_init="auto")
    labels: np.ndarray = kmeans.fit_predict(embeddings)
    centroids: np.ndarray = kmeans.cluster_centers_.astype(np.float32)

    db.execute(delete(OpportunityCluster))
    db.flush()

    dim = centroids.shape[1]
    new_clusters: list[OpportunityCluster] = []

    for cluster_idx in range(k):
        centroid = centroids[cluster_idx].tolist()
        member_mask = labels == cluster_idx
        member_opps = [rows[i] for i in range(len(rows)) if member_mask[i]]

        keywords = extract_cluster_keywords(member_opps)
        domains = dominant_domains(member_opps)
        version = centroid_version(centroid)

        cluster = OpportunityCluster(
            name=f"Cluster {cluster_idx + 1}",
            description=None,
            centroid=centroid,
            top_keywords=keywords,
            dominant_domains=domains,
            member_count=int(member_mask.sum()),
            faiss_index_id=cluster_idx,
            centroid_version=version,
            algorithm_meta={
                "algorithm": "kmeans",
                "k": k,
                "n_opportunities": len(rows),
                "recomputed_at": datetime.now(UTC).isoformat(),
            },
        )
        db.add(cluster)
        new_clusters.append(cluster)

    db.flush()

    for i, opp in enumerate(rows):
        cluster = new_clusters[labels[i]]
        opp.cluster_id = cluster.id
        opp.needs_cluster_assignment = False

    db.flush()

    index_flat = faiss.IndexFlatIP(dim)
    index = faiss.IndexIDMap(index_flat)
    faiss_ids = np.array([c.faiss_index_id for c in new_clusters], dtype=np.int64)
    index.add_with_ids(centroids, faiss_ids)

    new_id_to_cluster = {c.faiss_index_id: c.id for c in new_clusters}
    new_version = new_clusters[0].centroid_version if new_clusters else None
    
    set_faiss_state(index, new_id_to_cluster, new_version)

    update_cluster_stats(db)
    invalidate_cluster_cache(cache)

    logger.info(f"Full re-cluster complete — {k} clusters created")
    return {"action": "full_recluster", "clusters": k, "opportunities": len(rows)}

def incremental_cluster_assign(opps: list, embeddings: np.ndarray, db: Session) -> int:
    faiss_idx = get_faiss_index()
    if faiss_idx is None or faiss_idx.ntotal == 0 or len(opps) == 0:
        return 0

    query = embeddings.astype(np.float32)
    if query.ndim == 1:
        query = query.reshape(1, -1)

    _, faiss_ids = faiss_idx.search(query, 1)

    assigned = 0
    id_to_cluster_map = faiss_id_to_cluster()
    for opp, result_ids in zip(opps, faiss_ids):
        faiss_id = int(result_ids[0])
        cluster_db_id = id_to_cluster_map.get(faiss_id)
        if cluster_db_id is not None:
            opp.cluster_id = cluster_db_id
            opp.needs_cluster_assignment = False
            assigned += 1

    return assigned

def extract_cluster_keywords(opps: list, top_n: int = 10) -> list[str]:
    from collections import Counter
    import re
    stopwords = {"the", "and", "for", "with", "this", "that", "are", "from", "will", "have", "has", "been", "you", "your", "our", "their", "can", "may", "also", "other", "any", "all", "not", "but"}
    counter: Counter = Counter()
    for opp in opps:
        text = f"{opp.title} {' '.join(opp.tags or [])} {' '.join(opp.required_skills or [])}"
        words = re.findall(r"\b[a-z]{3,}\b", text.lower())
        counter.update(w for w in words if w not in stopwords)
    return [word for word, _ in counter.most_common(top_n)]

def dominant_domains(opps: list) -> list[str]:
    from collections import Counter
    counter: Counter = Counter(opp.domain.value if hasattr(opp.domain, "value") else str(opp.domain) for opp in opps)
    return [domain for domain, _ in counter.most_common()]

def update_cluster_stats(db: Session) -> None:
    from sqlalchemy import func, select, update
    from backend.models.cluster import OpportunityCluster
    from backend.models.opportunity import Opportunity
    counts = db.execute(select(Opportunity.cluster_id, func.count().label("cnt")).where(Opportunity.cluster_id.is_not(None)).group_by(Opportunity.cluster_id)).all()
    for row in counts:
        db.execute(update(OpportunityCluster).where(OpportunityCluster.id == row.cluster_id).values(member_count=row.cnt))
    db.flush()
