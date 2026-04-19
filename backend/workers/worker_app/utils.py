"""
utils.py — pure shared helper functions for the worker layer.

Rules:
  - No imports from worker_app submodules (no ml/, agents/, scrapers/, notifications/)
  - No Celery, no FastAPI, no async code
  - Every function is a pure transformation or a single DB read
  - Safe to import from any layer without circular dependencies
"""

from __future__ import annotations

import re
from collections import Counter
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from backend.models.opportunity import Opportunity
    from backend.models.user import User
    from backend.core.enums import NotificationType


# =============================================================================
# Embedding text builders
# =============================================================================

def build_embedding_text(opp: "Opportunity") -> str:
    """
    Builds the text string passed to the sentence-transformer encoder
    for an opportunity.

    Title is repeated intentionally — sentence-transformers average token
    embeddings, so doubling the title upweights it in the resulting vector
    relative to the longer but noisier description field.

    Description is truncated at 512 chars. Beyond that, the signal-to-noise
    ratio drops and encoding time increases for marginal quality gain.
    """
    parts = [
        opp.title,
        opp.title,
        opp.organization or "",
        " ".join(opp.tags or []),
        " ".join(opp.required_skills or []),
        (opp.description or "")[:512],
    ]
    return " ".join(p for p in parts if p).strip()


def build_user_profile_text(user: "User") -> str:
    """
    Builds the text string passed to the sentence-transformer encoder
    for a user profile.

    This text is embedded into the same vector space as opportunities,
    so the fields chosen here must semantically overlap with the fields
    used in build_embedding_text — skills ↔ required_skills,
    interests ↔ tags/domain, field_of_study ↔ title/organization.

    Falls back to "general student" so the encoder never receives an
    empty string, which would produce a zero vector and break cosine sim.
    """
    parts = [
        user.field_of_study or "",
        " ".join(user.interests or []),
        " ".join(user.skills or []),
        user.bio or "",
    ]
    text = " ".join(p for p in parts if p).strip()
    return text if text else "general student"


# =============================================================================
# Cluster labelling helpers
# =============================================================================

_STOPWORDS: frozenset[str] = frozenset({
    "the", "and", "for", "with", "this", "that", "are", "from",
    "will", "have", "has", "been", "you", "your", "our", "their",
    "can", "may", "also", "other", "any", "all", "not", "but",
    "its", "more", "into", "such", "than", "then", "when", "which",
    "who", "how", "was", "were", "they", "them", "some", "just",
    "about", "would", "could", "each", "very", "well", "only",
})


def extract_cluster_keywords(
    opps: "list[Opportunity]",
    top_n: int = 10,
) -> list[str]:
    """
    Extracts the most frequent meaningful terms across a cluster's
    opportunities. Used to auto-label clusters after KMeans.

    Pulls from title, tags, and required_skills — the three most
    signal-dense fields. Description is excluded because it's noisy
    and would dilute domain-specific terms.

    Returns top_n lowercase words, stopwords excluded, min 3 chars.
    """
    counter: Counter = Counter()
    for opp in opps:
        text = " ".join([
            opp.title,
            " ".join(opp.tags or []),
            " ".join(opp.required_skills or []),
        ])
        words = re.findall(r"\b[a-z]{3,}\b", text.lower())
        counter.update(w for w in words if w not in _STOPWORDS)
    return [word for word, _ in counter.most_common(top_n)]


def dominant_domains(opps: "list[Opportunity]") -> list[str]:
    """
    Returns a list of domain values sorted by frequency within a
    cluster — most common first.

    Used to populate OpportunityCluster.dominant_domains so the
    dashboard can show what a cluster is mostly about without loading
    all its members.
    """
    counter: Counter = Counter(
        opp.domain.value if hasattr(opp.domain, "value") else str(opp.domain)
        for opp in opps
    )
    return [domain for domain, _ in counter.most_common()]


# =============================================================================
# Notification deduplication
# =============================================================================

def notification_exists(
    db: "Session",
    user_id: int,
    opportunity_id: int,
    notification_type: "NotificationType",
) -> bool:
    """
    Returns True if a notification of the given type already exists
    for this (user, opportunity) pair.

    Called by every notifier before inserting a new Notification row
    to prevent duplicate alerts. Uses a cheap EXISTS query rather than
    loading the full row.

    Args:
        db:                Sync SQLAlchemy session (from Celery task).
        user_id:           Target user's DB id.
        opportunity_id:    Related opportunity's DB id.
        notification_type: The NotificationType enum value to check.

    Returns:
        True if a matching notification already exists, False otherwise.
    """
    from sqlalchemy import exists, select
    from backend.models.notification import Notification

    stmt = select(
        exists().where(
            Notification.user_id == user_id,
            Notification.opportunity_id == opportunity_id,
            Notification.type == notification_type,
        )
    )
    return bool(db.execute(stmt).scalar())


# =============================================================================
# Text cleaning
# =============================================================================

def clean_text(text: str, max_length: int = 2000) -> str:
    """
    Strips excessive whitespace and truncates to max_length.
    Used by scrapers before storing raw description text.
    """
    if not text:
        return ""
    cleaned = re.sub(r"\s+", " ", text).strip()
    return cleaned[:max_length]


def slugify(text: str) -> str:
    """
    Converts a string to a lowercase slug for use as a tag or keyword.
    e.g. "Machine Learning" → "machine-learning"
    """
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    return text.strip("-")


# =============================================================================
# Scoring utilities
# =============================================================================

def jaccard_overlap(set_a: set[str], set_b: set[str]) -> float:
    """
    Computes Jaccard similarity between two sets of strings.

    Used by scorer.py for skill overlap calculation.
    Returns 0.5 if either set is empty (neutral score — lack of
    specified requirements doesn't penalise the opportunity).

    Returns:
        Float in [0, 1]. 1.0 = identical sets, 0.0 = disjoint.
    """
    if not set_a or not set_b:
        return 0.5
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


def clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    """Clamps a float to [lo, hi]. Used in scoring to prevent out-of-range values."""
    return max(lo, min(hi, value))


def centroid_version_hash(centroid: list[float]) -> str:
    """Short SHA-1 fingerprint of a centroid vector. Stored in OpportunityCluster.centroid_version."""
    import hashlib
    import numpy as np
    return hashlib.sha1(np.array(centroid, dtype=np.float32).tobytes()).hexdigest()[:16]