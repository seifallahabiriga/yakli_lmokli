"""
clusterer.py — KMeans wrapper and drift detection for the cluster agent.

Responsibilities:
  - Fit KMeans on a matrix of embeddings
  - Compute drift ratio from DB counts
  - Decide between full re-cluster and incremental FAISS assignment
  - Provide cluster quality metrics

Rules:
  - No DB writes — returns labels and centroids, caller does the writing
  - No FAISS imports — faiss_store.py owns the index
  - No Celery, no async
  - All functions synchronous and pure where possible
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from backend.core.config import get_settings

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)
settings = get_settings()

# =============================================================================
# Constants
# =============================================================================

DRIFT_THRESHOLD: float = 0.10
"""
Fraction of embedded opportunities that are unassigned before a full
re-cluster is triggered instead of incremental FAISS assignment.

0.10 = if more than 10% of all embedded opportunities lack a cluster,
rebuild the entire KMeans model.

Rationale: at low drift (<10%) the existing centroids are still a
good approximation of the data distribution. FAISS nearest-centroid
assignment gives reasonable results without retraining.
At high drift (>10%) the centroids no longer represent the data well
and re-clustering produces meaningfully better assignments.
"""

MIN_OPPORTUNITIES_TO_CLUSTER: int = 20
"""
Minimum number of embedded opportunities required before any clustering
attempt. Below this, clusters are statistically meaningless and KMeans
is likely to produce degenerate results (k > n_samples).
"""


# =============================================================================
# Data classes
# =============================================================================

@dataclass
class ClusterResult:
    """
    Output of a KMeans fit run.

    Fields:
        labels:      np.ndarray of shape (n,), dtype int.
                     labels[i] is the cluster index (0..k-1) for opportunity i.
        centroids:   np.ndarray of shape (k, dim), dtype float32.
                     L2-normalised centroid vectors.
        k:           Number of clusters actually produced.
                     May be less than requested if n_samples < k.
        inertia:     KMeans within-cluster sum of squared distances.
                     Lower is better — use for quality monitoring.
        n_samples:   Total number of samples clustered.
    """
    labels: np.ndarray
    centroids: np.ndarray
    k: int
    inertia: float
    n_samples: int


@dataclass
class DriftReport:
    """
    Output of drift_check().

    Fields:
        n_embedded:    Total opportunities with embeddings.
        n_unassigned:  Opportunities with needs_cluster_assignment=True.
        drift_ratio:   n_unassigned / n_embedded (0.0 if n_embedded == 0).
        needs_recluster: True when drift exceeds DRIFT_THRESHOLD or no
                         FAISS index exists yet.
        reason:        Human-readable explanation for the decision.
    """
    n_embedded: int
    n_unassigned: int
    drift_ratio: float
    needs_recluster: bool
    reason: str


# =============================================================================
# Public API
# =============================================================================

def fit(
    embeddings: np.ndarray,
    k: int | None = None,
    random_state: int = 42,
) -> ClusterResult:
    """
    Runs KMeans on the provided embedding matrix.

    Args:
        embeddings:    np.ndarray of shape (n, dim), dtype float32.
                       Must be L2-normalised.
        k:             Number of clusters. Defaults to settings.CLUSTER_N_CLUSTERS.
                       Automatically capped at n_samples to prevent k > n.
        random_state:  Random seed for reproducibility.

    Returns:
        ClusterResult with labels, centroids, and quality metrics.

    Raises:
        ValueError: embeddings is empty or has fewer than 2 samples.
    """
    if embeddings.ndim != 2 or embeddings.shape[0] < 2:
        raise ValueError(
            f"embeddings must be a 2-D matrix with at least 2 rows, "
            f"got shape {embeddings.shape}"
        )

    n_samples, dim = embeddings.shape
    k_requested = k or settings.CLUSTER_N_CLUSTERS
    k_actual = min(k_requested, n_samples)

    if k_actual < k_requested:
        logger.warning(
            "Requested k=%d but only %d samples — using k=%d",
            k_requested, n_samples, k_actual,
        )

    logger.info(
        "Running KMeans k=%d on %d embeddings (dim=%d)",
        k_actual, n_samples, dim,
    )

    from sklearn.cluster import KMeans

    kmeans = KMeans(
        n_clusters=k_actual,
        init="k-means++",       # better initial centroids than random
        n_init="auto",          # sklearn ≥1.4 picks sensible default
        random_state=random_state,
        max_iter=300,
    )
    labels: np.ndarray = kmeans.fit_predict(embeddings)

    # KMeans centroids are not L2-normalised — normalise them so FAISS
    # inner-product search correctly approximates cosine similarity.
    raw_centroids: np.ndarray = kmeans.cluster_centers_.astype(np.float32)
    norms = np.linalg.norm(raw_centroids, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)   # avoid division by zero
    centroids = raw_centroids / norms

    result = ClusterResult(
        labels=labels,
        centroids=centroids,
        k=k_actual,
        inertia=float(kmeans.inertia_),
        n_samples=n_samples,
    )

    logger.info(
        "KMeans complete — k=%d, inertia=%.4f",
        k_actual, result.inertia,
    )
    return result


def drift_check(db: "Session") -> DriftReport:
    """
    Reads two counts from the DB and evaluates whether a full re-cluster
    is needed or incremental FAISS assignment is sufficient.

    Also checks whether the FAISS index is ready — if not, forces a
    full re-cluster regardless of drift ratio.

    Args:
        db: Sync SQLAlchemy session.

    Returns:
        DriftReport with the decision and supporting numbers.
    """
    from sqlalchemy import func, select
    from backend.models.opportunity import Opportunity
    from backend.workers.worker_app.ml.faiss_store import is_ready

    n_embedded: int = db.execute(
        select(func.count()).select_from(Opportunity).where(
            Opportunity.embedding.is_not(None)
        )
    ).scalar_one()

    n_unassigned: int = db.execute(
        select(func.count()).select_from(Opportunity).where(
            Opportunity.needs_cluster_assignment.is_(True)
        )
    ).scalar_one()

    if n_embedded == 0:
        return DriftReport(
            n_embedded=0,
            n_unassigned=0,
            drift_ratio=0.0,
            needs_recluster=False,
            reason="no_embeddings",
        )

    if n_embedded < MIN_OPPORTUNITIES_TO_CLUSTER:
        return DriftReport(
            n_embedded=n_embedded,
            n_unassigned=n_unassigned,
            drift_ratio=0.0,
            needs_recluster=False,
            reason=f"insufficient_data ({n_embedded} < {MIN_OPPORTUNITIES_TO_CLUSTER})",
        )

    drift_ratio = n_unassigned / n_embedded

    if not is_ready():
        return DriftReport(
            n_embedded=n_embedded,
            n_unassigned=n_unassigned,
            drift_ratio=drift_ratio,
            needs_recluster=True,
            reason="no_faiss_index",
        )

    if drift_ratio > DRIFT_THRESHOLD:
        return DriftReport(
            n_embedded=n_embedded,
            n_unassigned=n_unassigned,
            drift_ratio=drift_ratio,
            needs_recluster=True,
            reason=f"drift_exceeded ({drift_ratio:.1%} > {DRIFT_THRESHOLD:.1%})",
        )

    return DriftReport(
        n_embedded=n_embedded,
        n_unassigned=n_unassigned,
        drift_ratio=drift_ratio,
        needs_recluster=False,
        reason=f"drift_ok ({drift_ratio:.1%} <= {DRIFT_THRESHOLD:.1%})",
    )


def load_all_embeddings(db: "Session") -> tuple[np.ndarray, list[int]]:
    """
    Loads all opportunity embeddings from the DB into a numpy matrix.

    Used by cluster_agent before a full re-cluster run.

    Returns:
        Tuple of:
          - np.ndarray of shape (n, dim), dtype float32
          - list[int] of opportunity DB ids, parallel to the matrix rows
            so labels[i] can be mapped back to opp_ids[i]

    Raises:
        ValueError: no opportunities with embeddings exist.
    """
    from sqlalchemy import select
    from backend.models.opportunity import Opportunity

    rows = db.execute(
        select(Opportunity.id, Opportunity.embedding).where(
            Opportunity.embedding.is_not(None)
        )
    ).all()

    if not rows:
        raise ValueError("No embedded opportunities found in DB")

    opp_ids = [row.id for row in rows]
    embeddings = np.array(
        [row.embedding for row in rows],
        dtype=np.float32,
    )

    logger.info(
        "Loaded %d embeddings from DB (dim=%d)",
        len(opp_ids), embeddings.shape[1],
    )
    return embeddings, opp_ids


def load_unassigned_embeddings(db: "Session") -> tuple[np.ndarray, list[int]]:
    """
    Loads only the embeddings of opportunities flagged for cluster assignment.

    Used by cluster_agent during incremental assignment — much cheaper
    than loading all embeddings when drift is low.

    Returns:
        Same shape as load_all_embeddings.
        Returns (empty array, []) when no unassigned opportunities exist.
    """
    from sqlalchemy import select
    from backend.models.opportunity import Opportunity

    rows = db.execute(
        select(Opportunity.id, Opportunity.embedding).where(
            Opportunity.needs_cluster_assignment.is_(True),
            Opportunity.embedding.is_not(None),
        )
    ).all()

    if not rows:
        return np.empty((0, 0), dtype=np.float32), []

    opp_ids = [row.id for row in rows]
    embeddings = np.array(
        [row.embedding for row in rows],
        dtype=np.float32,
    )
    return embeddings, opp_ids


# =============================================================================
# Quality metrics
# =============================================================================

def silhouette_score_sample(
    embeddings: np.ndarray,
    labels: np.ndarray,
    max_samples: int = 1000,
) -> float | None:
    """
    Computes a silhouette score on a random sample of embeddings.

    Silhouette score measures cluster cohesion and separation:
      +1.0 → perfectly separated clusters
       0.0 → overlapping clusters
      -1.0 → misassigned samples

    Sampling is used because full silhouette is O(n²) — too slow for
    large datasets. 1000 samples gives a reliable estimate.

    Returns None if sklearn raises (e.g. only 1 cluster).
    """
    try:
        from sklearn.metrics import silhouette_score

        n = len(embeddings)
        if n <= max_samples:
            sample_emb, sample_labels = embeddings, labels
        else:
            rng = np.random.default_rng(42)
            idx = rng.choice(n, size=max_samples, replace=False)
            sample_emb = embeddings[idx]
            sample_labels = labels[idx]

        return float(silhouette_score(sample_emb, sample_labels, metric="cosine"))

    except Exception as exc:
        logger.debug("Silhouette score unavailable: %s", exc)
        return None