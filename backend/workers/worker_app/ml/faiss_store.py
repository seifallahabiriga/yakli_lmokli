import os
import json
import logging
import hashlib
from datetime import UTC, datetime
from typing import TYPE_CHECKING
import numpy as np
from backend.core.config import get_settings

if TYPE_CHECKING:
    from redis import Redis

logger = logging.getLogger(__name__)
settings = get_settings()

_faiss_index = None
_faiss_id_to_cluster: dict[int, int] = {}
_faiss_version: str | None = None

def get_faiss_index():
    global _faiss_index, _faiss_id_to_cluster, _faiss_version
    if _faiss_index is not None:
        return _faiss_index
    index_path = _faiss_index_path()
    meta_path = _faiss_meta_path()
    if os.path.exists(index_path) and os.path.exists(meta_path):
        import faiss
        logger.info(f"Loading FAISS index from disk: {index_path}")
        _faiss_index = faiss.read_index(index_path)
        with open(meta_path) as f:
            meta = json.load(f)
        _faiss_id_to_cluster = {int(k): v for k, v in meta["id_map"].items()}
        _faiss_version = meta.get("version")
        logger.info(f"FAISS index loaded — {_faiss_index.ntotal} centroids, version {_faiss_version}")
    return _faiss_index

def faiss_id_to_cluster():
    global _faiss_id_to_cluster
    return _faiss_id_to_cluster

def set_faiss_state(index, id_to_cluster: dict, version: str | None):
    global _faiss_index, _faiss_id_to_cluster, _faiss_version
    _faiss_index = index
    _faiss_id_to_cluster = id_to_cluster
    _faiss_version = version

def _faiss_index_path() -> str:
    os.makedirs(settings.FAISS_INDEX_PATH, exist_ok=True)
    return os.path.join(settings.FAISS_INDEX_PATH, "clusters.index")

def _faiss_meta_path() -> str:
    return os.path.join(settings.FAISS_INDEX_PATH, "clusters_meta.json")

def centroid_version(centroid: list[float]) -> str:
    return hashlib.sha1(np.array(centroid, dtype=np.float32).tobytes()).hexdigest()[:16]

def invalidate_cluster_cache(cache: Redis) -> None:
    keys = cache.keys("clusters:*")
    if keys:
        cache.delete(*keys)

def save_faiss_index() -> dict:
    import faiss
    faiss_idx = get_faiss_index()
    if faiss_idx is None:
        logger.info("FAISS persistence: no index in memory, skipping")
        return {"saved": False, "reason": "no_index"}
    index_path = _faiss_index_path()
    meta_path = _faiss_meta_path()
    faiss.write_index(faiss_idx, index_path)
    with open(meta_path, "w") as f:
        json.dump(
            {
                "id_map": {str(k): v for k, v in _faiss_id_to_cluster.items()},
                "version": _faiss_version,
                "saved_at": datetime.now(UTC).isoformat(),
            },
            f,
        )
    logger.info(f"FAISS index saved to {index_path} ({faiss_idx.ntotal} centroids)")
    return {"saved": True, "path": index_path, "centroids": faiss_idx.ntotal}
