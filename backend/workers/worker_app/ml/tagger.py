"""
tagger.py — spaCy singleton for NER and keyword extraction.

Rules:
  - spaCy model loaded once per worker process (module-level singleton)
  - All public functions are synchronous
  - No DB, no Redis, no Celery imports
  - Input is raw text, output is plain Python sets/lists
  - Degrades gracefully if spaCy model is missing — logs warning, returns empty
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING

from backend.core.config import get_settings
from backend.workers.worker_app.utils import _STOPWORDS, extract_cluster_keywords

if TYPE_CHECKING:
    import spacy
    from spacy.language import Language
    from backend.models.opportunity import Opportunity

logger = logging.getLogger(__name__)
settings = get_settings()

# =============================================================================
# Singleton
# =============================================================================

_nlp: "Language | None" = None
_lock = threading.Lock()
_load_failed: bool = False        # avoid retrying a failed load on every task


def get_nlp() -> "Language | None":
    """
    Returns the shared spaCy Language instance, loading it on first call.

    Returns None if the model is not installed — callers must handle
    this gracefully by skipping NLP enrichment rather than crashing.

    Thread-safe: same double-checked locking pattern as embedder.py.
    """
    global _nlp, _load_failed

    if _nlp is not None:
        return _nlp
    if _load_failed:
        return None

    with _lock:
        if _nlp is not None:
            return _nlp
        if _load_failed:
            return None

        try:
            import spacy as _spacy

            logger.info("Loading spaCy model: %s", settings.SPACY_MODEL)
            _nlp = _spacy.load(settings.SPACY_MODEL)
            logger.info("spaCy model loaded successfully")
        except OSError:
            logger.warning(
                "spaCy model '%s' not found. "
                "Run: python -m spacy download %s. "
                "NLP tag enrichment will be skipped.",
                settings.SPACY_MODEL,
                settings.SPACY_MODEL,
            )
            _load_failed = True

    return _nlp


# =============================================================================
# Public API
# =============================================================================

def extract_tags(title: str, description: str) -> set[str]:
    """
    Extracts named entities and salient noun chunks from opportunity text
    and returns them as a set of lowercase tag strings.

    These tags are merged into Opportunity.tags after scraping, enriching
    the keyword surface available for full-text search and cluster labelling.

    Entity types extracted:
      - ORG  → organisation names ("Google", "INRIA", "CNRS")
      - GPE  → geopolitical entities — cities, countries ("Paris", "Tunisia")
      - PRODUCT → named tools/frameworks ("PyTorch", "TensorFlow")

    Noun chunks: only the root token of each chunk is kept if it is not a
    stopword, not punctuation, and at least 3 characters long. This avoids
    adding generic filler like "the opportunity" or "a position".

    Returns empty set (not None) when spaCy is unavailable or text is empty,
    so callers can always do `opp.tags = list(existing | extract_tags(...))`.

    Args:
        title:       Opportunity title string.
        description: Opportunity description string. Truncated internally
                     to 1000 chars to keep inference time predictable.

    Returns:
        set[str] — lowercase tag strings, may be empty.
    """
    if not title and not description:
        return set()

    nlp = get_nlp()
    if nlp is None:
        return set()

    try:
        text = f"{title}. {description[:1000]}"
        doc = nlp(text)
        tags: set[str] = set()

        # Named entities
        for ent in doc.ents:
            if ent.label_ in ("ORG", "GPE", "PRODUCT"):
                cleaned = ent.text.strip().lower()
                if len(cleaned) >= 2:
                    tags.add(cleaned)

        # Noun chunk roots — salient domain terms
        for chunk in doc.noun_chunks:
            root = chunk.root
            if (
                not root.is_stop
                and not root.is_punct
                and not root.is_space
                and len(root.text) >= 3
            ):
                tags.add(root.text.lower().strip())

        # Remove any stopwords that slipped through
        tags -= _STOPWORDS

        return tags

    except Exception as exc:
        logger.warning("extract_tags failed: %s", exc)
        return set()


def extract_keywords_from_texts(
    texts: list[str],
    top_n: int = 15,
) -> list[str]:
    """
    Extracts the most frequent meaningful tokens across a list of texts.
    Thin wrapper around the Counter-based approach in utils.py, but uses
    spaCy tokenisation when available for better quality.

    Used by cluster_agent.py to auto-label new clusters.

    Args:
        texts:  List of raw text strings (e.g. concatenated title+tags
                for each opportunity in a cluster).
        top_n:  Maximum number of keywords to return.

    Returns:
        list[str] — top_n lowercase keywords, most frequent first.
    """
    if not texts:
        return []

    nlp = get_nlp()

    if nlp is None:
        # Fallback: regex-based extraction from utils
        from collections import Counter
        import re
        counter: Counter = Counter()
        for text in texts:
            words = re.findall(r"\b[a-z]{3,}\b", text.lower())
            counter.update(w for w in words if w not in _STOPWORDS)
        return [w for w, _ in counter.most_common(top_n)]

    try:
        from collections import Counter
        counter = Counter()

        for text in texts:
            doc = nlp(text[:500])   # cap per-text to keep total time bounded
            for token in doc:
                if (
                    not token.is_stop
                    and not token.is_punct
                    and not token.is_space
                    and token.is_alpha
                    and len(token.text) >= 3
                    and token.text.lower() not in _STOPWORDS
                ):
                    counter[token.lemma_.lower()] += 1

        return [lemma for lemma, _ in counter.most_common(top_n)]

    except Exception as exc:
        logger.warning("extract_keywords_from_texts failed: %s", exc)
        return []


def enrich_opportunity_tags(
    opp: "Opportunity",
) -> list[str]:
    """
    Merges NLP-extracted tags into an opportunity's existing tag list.

    Convenience wrapper used by classifier_agent.py — handles the
    set merge and deduplication in one call.

    Args:
        opp: SQLAlchemy Opportunity instance (mutated in place by caller).

    Returns:
        New merged tag list as list[str].
        The caller is responsible for assigning it back to opp.tags.
    """
    existing = set(opp.tags or [])
    extracted = extract_tags(opp.title, opp.description or "")
    merged = existing | extracted
    return sorted(merged)           # sorted for deterministic DB storage