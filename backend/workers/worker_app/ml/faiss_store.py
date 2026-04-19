"""
faiss_store.py — FAISS index singleton for approximate nearest-neighbour
cluster centroid search.

Responsibilities:
  - Hold one IndexIDMap (wrapping IndexFlatIP) per worker process
  - Load from disk on first call so restarts are fast
  - Expose build / search / persist operations
  - Track centroid version so coordinator can detect stale index

Rules:
  - No DB, no Redis, no Celery imports
  - All functions synchronous
  - Thread-safe singleton load via threading.Lock
  - Degrades gracefully if faiss not installed (returns None from get_index)
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
from typing import TYPE_CHECKING

import numpy as np

from backend.core.config import get_settings

if TYPE_CHECKING:
    import faiss as _faiss_type

logger = logging.getLogger(__name__)
settings = get_settings()

# =============================================================================
# Module-level state
# =============================================================================

_index: "_faiss_type.IndexIDMap | None" = None
_id_to_cluster: dict[int, int] = {}   # faiss_index_id → cluster DB primary key
_version: str | None = None           # SHA-1 of last-built centroid matrix
_lock = threading.Lock()
_load_failed: bool = False


# =============================================================================
# Path helpers
# =============================================================================

def _index_path() -> str:
    os.makedirs(settings.FAISS_INDEX_PATH, exist_ok=True)
    return os.path.join(settings.FAISS_INDEX_PATH, "clusters.index")


def _meta_path() -> str:
    return os.path.join(settings.FAISS_INDEX_PATH, "clusters_meta.json")


# =============================================================================
# Singleton access
# =============================================================================

def get_index() -> "_faiss_type.IndexIDMap | None":
    """
    Returns the in-memory FAISS index, loading from disk on first call.

    Returns None when:
      - faiss-cpu is not installed
      - No persisted index exists on disk yet (first run before clustering)
      - A previous load attempt failed

    Callers must handle None — coordinator checks this before deciding
    whether to run incremental assignment or a full re-cluster.
    """
    global _index, _id_to_cluster, _version, _load_failed

    if _index is not None:
        return _index
    if _load_failed:
        return None

    with _lock:
        if _index is not None:
            return _index
        if _load_failed:
            return None

        _load_from_disk()

    return _index


def is_ready() -> bool:
    """Returns True if the index is loaded and contains at least one centroid."""
    idx = get_index()
    return idx is not None and idx.ntotal > 0


def current_version() -> str | None:
    """Returns the centroid version string of the current in-memory index."""
    return _version


# =============================================================================
# Build — full rebuild from KMeans centroids
# =============================================================================

def build_index(
    centroids: np.ndarray,
    faiss_ids: list[int],
    cluster_db_ids: list[int],
) -> None:
    """
    Builds a fresh FAISS IndexIDMap from KMeans centroids.

    Called by cluster_agent after a full KMeans re-cluster.
    Replaces whatever was in memory — old index is discarded.

    Args:
        centroids:      np.ndarray of shape (k, dim), float32.
                        Must be L2-normalised (dot product == cosine sim).
        faiss_ids:      List of integer IDs to assign in the FAISS index.
                        Corresponds to OpportunityCluster.faiss_index_id.
        cluster_db_ids: List of OpportunityCluster.id (DB primary keys).
                        Parallel to faiss_ids — same length, same order.

    Raises:
        ValueError: centroids and faiss_ids have different lengths.
        ImportError: faiss-cpu is not installed.
    """
    global _index, _id_to_cluster, _version

    if len(faiss_ids) != len(cluster_db_ids):
        raise ValueError(
            f"faiss_ids length ({len(faiss_ids)}) != "
            f"cluster_db_ids length ({len(cluster_db_ids)})"
        )
    if len(faiss_ids) != len(centroids):
        raise ValueError(
            f"faiss_ids length ({len(faiss_ids)}) != "
            f"centroids rows ({len(centroids)})"
        )

    import faiss

    centroids_f32 = centroids.astype(np.float32)
    dim = centroids_f32.shape[1]

    # IndexFlatIP + L2-normalised vectors = cosine similarity search
    flat = faiss.IndexFlatIP(dim)
    index = faiss.IndexIDMap(flat)
    index.add_with_ids(
        centroids_f32,
        np.array(faiss_ids, dtype=np.int64),
    )

    with _lock:
        _index = index
        _id_to_cluster = dict(zip(faiss_ids, cluster_db_ids))
        _version = _compute_version(centroids_f32)

    logger.info(
        "FAISS index built — %d centroids, dim=%d, version=%s",
        index.ntotal, dim, _version,
    )


# =============================================================================
# Search — nearest centroid for one or many embeddings
# =============================================================================

def search_nearest(embedding: np.ndarray) -> int | None:
    """
    Returns the DB cluster id whose centroid is nearest to the given embedding.

    Args:
        embedding: 1-D float32 array of shape (dim,). Must be L2-normalised.

    Returns:
        OpportunityCluster.id (DB primary key), or None if:
          - No index is loaded
          - The returned FAISS id has no mapping (should not happen in practice)
    """
    idx = get_index()
    if idx is None or idx.ntotal == 0:
        return None

    query = embedding.astype(np.float32).reshape(1, -1)
    _, ids = idx.search(query, 1)          # shape: (1, 1)
    faiss_id = int(ids[0][0])

    return _id_to_cluster.get(faiss_id)


def search_nearest_batch(
    embeddings: np.ndarray,
) -> list[int | None]:
    """
    Batch version of search_nearest.

    Args:
        embeddings: np.ndarray of shape (n, dim), float32, L2-normalised.

    Returns:
        List of length n — each element is a cluster DB id or None.
    """
    idx = get_index()
    if idx is None or idx.ntotal == 0:
        return [None] * len(embeddings)

    query = embeddings.astype(np.float32)
    _, ids = idx.search(query, 1)          # shape: (n, 1)

    return [
        _id_to_cluster.get(int(row[0]))
        for row in ids
    ]


# =============================================================================
# Persistence
# =============================================================================

def save_index() -> dict:
    """
    Serializes the in-memory FAISS index and metadata to disk.

    Called by the persist_faiss_index Celery task every hour.
    On worker restart, get_index() will reload from these files.

    Returns:
        Dict describing the save result — stored as Celery task result.
    """
    idx = get_index()
    if idx is None:
        logger.info("FAISS save skipped — no index in memory")
        return {"saved": False, "reason": "no_index"}

    import faiss

    index_path = _index_path()
    meta_path = _meta_path()

    faiss.write_index(idx, index_path)

    with open(meta_path, "w") as f:
        json.dump(
            {
                "id_map": {str(k): v for k, v in _id_to_cluster.items()},
                "version": _version,
                "ntotal": idx.ntotal,
            },
            f,
            indent=2,
        )

    logger.info(
        "FAISS index saved — path=%s, centroids=%d, version=%s",
        index_path, idx.ntotal, _version,
    )
    return {
        "saved": True,
        "path": index_path,
        "centroids": idx.ntotal,
        "version": _version,
    }


def _load_from_disk() -> None:
    """
    Internal — loads index + metadata from disk into module globals.
    Called once inside the lock during get_index().
    """
    global _index, _id_to_cluster, _version, _load_failed

    index_path = _index_path()
    meta_path = _meta_path()

    if not os.path.exists(index_path) or not os.path.exists(meta_path):
        logger.info(
            "No persisted FAISS index found at %s — "
            "will build from scratch on first cluster run",
            index_path,
        )
        return

    try:
        import faiss

        logger.info("Loading FAISS index from disk: %s", index_path)
        _index = faiss.read_index(index_path)

        with open(meta_path) as f:
            meta = json.load(f)

        _id_to_cluster = {int(k): v for k, v in meta["id_map"].items()}
        _version = meta.get("version")

        logger.info(
            "FAISS index loaded — centroids=%d, version=%s",
            _index.ntotal, _version,
        )

    except Exception as exc:
        logger.error("Failed to load FAISS index from disk: %s", exc)
        _load_failed = True


# =============================================================================
# Version helpers
# =============================================================================

def _compute_version(centroids: np.ndarray) -> str:
    """
    Computes a short SHA-1 fingerprint of the centroid matrix.

    Used by coordinator to detect when the in-memory index was built
    from different centroids than what's stored in the DB — triggering
    a full rebuild rather than an incremental assignment.

    Returns a 16-char hex string.
    """
    return hashlib.sha1(centroids.tobytes()).hexdigest()[:16]


def centroid_version(centroid: list[float]) -> str:
    """
    Public helper — computes the version string for a single centroid vector.

    Called by cluster_agent when writing OpportunityCluster.centroid_version
    to the DB so the coordinator can compare DB version vs index version.
    """
    arr = np.array(centroid, dtype=np.float32)
    return hashlib.sha1(arr.tobytes()).hexdigest()[:16]


def is_stale(db_version: str) -> bool:
    """
    Returns True if the in-memory index was built from different centroids
    than the version stored in the DB.

    Args:
        db_version: OpportunityCluster.centroid_version from the DB
                    (the version of the last full re-cluster).

    Returns:
        True  → index needs to be rebuilt before incremental assignment.
        False → index matches the DB — safe to do incremental assignment.
    """
    if _version is None:
        return True
    return _version != db_version