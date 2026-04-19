"""
embedder.py — sentence-transformer singleton for text encoding.

Rules:
  - Model is loaded once per worker process (module-level singleton)
  - All public functions are synchronous (called from Celery tasks)
  - No DB, no Redis, no Celery imports
  - Output vectors are always L2-normalised so dot product == cosine similarity
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING

import numpy as np

from backend.core.config import get_settings

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)
settings = get_settings()

# =============================================================================
# Singleton — one model instance per worker process
# =============================================================================

_encoder: "SentenceTransformer | None" = None
_lock = threading.Lock()          # guard against race on first load


def get_encoder() -> "SentenceTransformer":
    """
    Returns the shared SentenceTransformer instance, loading it on first call.

    Thread-safe: uses a lock so two Celery threads racing at startup
    don't load the model twice. After the first load the lock is never
    contested again (double-checked locking pattern).

    Model is ~90 MB on disk and takes ~2 s to load on CPU.
    Loading once per process and reusing across tasks is mandatory.
    """
    global _encoder

    if _encoder is not None:
        return _encoder

    with _lock:
        if _encoder is not None:          # re-check inside lock
            return _encoder

        logger.info(
            "Loading sentence-transformer model: %s", settings.EMBEDDING_MODEL
        )
        from sentence_transformers import SentenceTransformer

        _encoder = SentenceTransformer(settings.EMBEDDING_MODEL)
        logger.info("Sentence-transformer model loaded successfully")

    return _encoder


# =============================================================================
# Public encoding API
# =============================================================================

def encode(
    texts: list[str],
    batch_size: int = 32,
    show_progress: bool = False,
) -> np.ndarray:
    """
    Encodes a list of texts into L2-normalised embedding vectors.

    Args:
        texts:         List of strings to encode. Must be non-empty.
                       Empty strings produce near-zero vectors — callers
                       should filter or replace them before passing here.
        batch_size:    Number of texts per forward pass. 32 is a safe
                       default for CPU; increase to 64–128 if running on GPU.
        show_progress: Whether to display a tqdm progress bar. Leave False
                       in production — progress bars break structured logs.

    Returns:
        np.ndarray of shape (len(texts), embedding_dim), dtype float32.
        Rows are L2-normalised — ||row|| == 1.0 for every row.
        Dot product between two rows equals their cosine similarity.

    Raises:
        ValueError: texts is empty.
    """
    if not texts:
        raise ValueError("texts must be a non-empty list")

    encoder = get_encoder()

    vectors: np.ndarray = encoder.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=show_progress,
        normalize_embeddings=True,   # L2-normalise in-library (faster than post-hoc)
        convert_to_numpy=True,
    )

    # Defensive: ensure float32 regardless of model output dtype
    return vectors.astype(np.float32)


def encode_one(text: str) -> np.ndarray:
    """
    Encodes a single text string into an L2-normalised embedding vector.

    Convenience wrapper for cases where only one text needs encoding
    (e.g. embedding a single newly scraped opportunity, or building a
    user profile vector for on-demand recommendation recompute).

    Returns:
        np.ndarray of shape (embedding_dim,), dtype float32.
    """
    result = encode([text], batch_size=1)
    return result[0]


def embedding_dim() -> int:
    """
    Returns the dimensionality of the embedding vectors produced by the
    current model. Used by faiss_store.py when initialising the index.

    For all-MiniLM-L6-v2 this is 384.
    For all-mpnet-base-v2 this is 768.
    """
    return get_encoder().get_sentence_embedding_dimension()


# =============================================================================
# Validation helpers
# =============================================================================

def assert_normalised(vectors: np.ndarray, tol: float = 1e-5) -> None:
    """
    Asserts that all rows of vectors are L2-normalised.
    Call in tests to verify encode() output is correct.

    Raises:
        AssertionError: any row norm deviates from 1.0 by more than tol.
    """
    norms = np.linalg.norm(vectors, axis=1)
    assert np.allclose(norms, 1.0, atol=tol), (
        f"Vectors are not L2-normalised. "
        f"Min norm: {norms.min():.6f}, Max norm: {norms.max():.6f}"
    )