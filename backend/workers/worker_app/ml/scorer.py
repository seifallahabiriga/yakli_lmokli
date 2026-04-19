"""
scorer.py — pure opportunity relevance scoring.

Rules:
  - No DB access, no Redis, no Celery, no ML model loading
  - Inputs are plain Python objects (User, Opportunity, float, datetime)
  - Output is (float, dict) — composite score + breakdown
  - Fully unit-testable with no infrastructure running
  - All signal functions are private and independently testable
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from backend.workers.worker_app.utils import clamp, jaccard_overlap

if TYPE_CHECKING:
    from backend.models.opportunity import Opportunity
    from backend.models.user import User


# =============================================================================
# Scoring weights
# =============================================================================

WEIGHTS: dict[str, float] = {
    "semantic_similarity": 0.35,   # cosine sim between profile and opp embeddings
    "skill_overlap":       0.25,   # jaccard(user.skills, opp.required_skills)
    "domain_match":        0.15,   # user interest vs opp domain
    "level_match":         0.10,   # academic_level vs opp level
    "deadline_proximity":  0.08,   # urgency signal — sweet spot 2–8 weeks
    "location_preference": 0.07,   # remote/onsite preference match
}

assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9, "Weights must sum to 1.0"

# Minimum composite score to store a recommendation.
# Opportunities below this threshold are not worth surfacing.
MIN_SCORE_THRESHOLD: float = 0.20


# =============================================================================
# Public interface
# =============================================================================

def score_opportunity(
    user: "User",
    opp: "Opportunity",
    semantic_sim: float,
    now: datetime,
) -> tuple[float, dict[str, float]]:
    """
    Computes a composite relevance score for one (user, opportunity) pair.

    Args:
        user:         SQLAlchemy User ORM instance.
        opp:          SQLAlchemy Opportunity ORM instance.
        semantic_sim: Cosine similarity between user profile embedding
                      and opportunity embedding. Must be in [-1, 1] but
                      realistically in [0, 1] for normalized vectors.
        now:          Current UTC datetime for deadline proximity calculation.

    Returns:
        Tuple of:
          - composite score in [0, 1] (higher = more relevant)
          - breakdown dict mapping signal name → signal score
            for display in the recommendation explanation UI
    """
    breakdown: dict[str, float] = {
        "semantic_similarity": _semantic(semantic_sim),
        "skill_overlap":       _skill_overlap(user, opp),
        "domain_match":        _domain_match(user, opp),
        "level_match":         _level_match(user, opp),
        "deadline_proximity":  _deadline_proximity(opp, now),
        "location_preference": _location_preference(user, opp),
    }

    composite = sum(
        breakdown[signal] * weight
        for signal, weight in WEIGHTS.items()
    )

    return round(clamp(composite), 4), {
        k: round(v, 4) for k, v in breakdown.items()
    }


def is_worth_storing(score: float) -> bool:
    """Returns True if the score clears the minimum threshold."""
    return score >= MIN_SCORE_THRESHOLD


# =============================================================================
# Signal functions — each returns a float in [0, 1]
# =============================================================================

def _semantic(sim: float) -> float:
    """
    Clamps the raw cosine similarity to [0, 1].

    Cosine similarity on L2-normalized vectors is already in [-1, 1].
    Negative values mean the texts are semantically opposite — we treat
    those as 0 rather than penalising further, since a score of 0 already
    means no semantic match.
    """
    return clamp(float(sim), 0.0, 1.0)


def _skill_overlap(user: "User", opp: "Opportunity") -> float:
    """
    Jaccard similarity between the user's skills and the opportunity's
    required skills (both normalised to lowercase).

    Returns 0.5 when either set is empty — see utils.jaccard_overlap
    for the rationale.
    """
    user_skills = {s.lower() for s in (user.skills or [])}
    opp_skills  = {s.lower() for s in (opp.required_skills or [])}
    return jaccard_overlap(user_skills, opp_skills)


def _domain_match(user: "User", opp: "Opportunity") -> float:
    """
    Checks whether the opportunity's domain appears in the user's interests.

    Three-tier score:
      1.0 — exact domain match in user interests
      0.6 — partial match: any opp tag appears in user interests
      0.3 — no match (but not zero — domain mismatch is a soft signal)

    The 0.3 floor prevents domain mismatch from completely burying
    an otherwise highly relevant opportunity.
    """
    opp_domain = (
        opp.domain.value
        if hasattr(opp.domain, "value")
        else str(opp.domain)
    )
    user_interests = {i.lower() for i in (user.interests or [])}
    opp_tags       = {t.lower() for t in (opp.tags or [])}

    if opp_domain in user_interests:
        return 1.0

    if user_interests & opp_tags:
        return 0.6

    return 0.3


def _level_match(user: "User", opp: "Opportunity") -> float:
    """
    Compares the user's academic level with the opportunity's target level.

    Scoring:
      1.0 — exact match
      0.8 — opp is open to all levels
      0.8 — user's level is unknown (can't penalise)
      0.5 — adjacent levels (one step apart in the academic ladder)
      0.1 — clear mismatch (e.g. bachelor applying to postdoc)

    Adjacent pairs: (bachelor↔master), (master↔phd), (phd↔postdoc)
    """
    _ADJACENTS: set[frozenset[str]] = {
        frozenset({"bachelor", "master"}),
        frozenset({"master", "phd"}),
        frozenset({"phd", "postdoc"}),
        frozenset({"postdoc", "professor"}),
    }

    opp_level  = (
        opp.level.value
        if hasattr(opp.level, "value")
        else str(opp.level)
    )
    user_level = (
        user.academic_level.value
        if user.academic_level and hasattr(user.academic_level, "value")
        else None
    )

    if opp_level == "all":
        return 0.8

    if user_level is None:
        return 0.8

    if opp_level == user_level:
        return 1.0

    if frozenset({opp_level, user_level}) in _ADJACENTS:
        return 0.5

    return 0.1


def _deadline_proximity(opp: "Opportunity", now: datetime) -> float:
    """
    Converts deadline distance into a relevance signal.

    The goal is to surface opportunities while the user still has time
    to prepare a strong application, not so early they forget and not
    so late they're scrambling.

    Scoring bands (days until deadline):
      < 0    → 0.0  already expired — should not appear (filtered upstream)
      0–7    → 1.0  urgent — deadline this week
      8–21   → 0.9  high — 1–3 weeks left, optimal application window
      22–60  → 0.7  medium — still very relevant
      61–120 → 0.4  low — months away, less urgent
      > 120  → 0.2  distant — keep in feed but deprioritise
      None   → 0.5  no deadline (rolling) — neutral score
    """
    if opp.deadline is None:
        return 0.5

    # Ensure both datetimes are comparable (both tz-aware or both naive)
    deadline = opp.deadline
    if deadline.tzinfo is not None and now.tzinfo is None:
        from datetime import timezone
        now = now.replace(tzinfo=timezone.utc)
    elif deadline.tzinfo is None and now.tzinfo is not None:
        deadline = deadline.replace(tzinfo=now.tzinfo)

    days_left = (deadline - now).days

    if days_left < 0:
        return 0.0
    if days_left <= 7:
        return 1.0
    if days_left <= 21:
        return 0.9
    if days_left <= 60:
        return 0.7
    if days_left <= 120:
        return 0.4
    return 0.2


def _location_preference(user: "User", opp: "Opportunity") -> float:
    """
    Checks whether the opportunity's location type matches the user's
    stated preferences (stored in user.preferences["locations"]).

    Scoring:
      1.0 — opp location type is in user's preferred locations
      0.7 — user has no stated preference (neutral)
      0.4 — mismatch (e.g. user wants remote, opp is onsite)

    Remote is treated as universally acceptable — if a user prefers
    onsite but the opp is remote, we still give a partial score (0.6)
    since remote is generally an acceptable fallback.
    """
    preferred = [
        loc.lower()
        for loc in user.preferences.get("locations", [])
    ]
    opp_loc = (
        opp.location_type.value
        if hasattr(opp.location_type, "value")
        else str(opp.location_type)
    ).lower()

    if not preferred:
        return 0.7

    if opp_loc in preferred:
        return 1.0

    # Remote as acceptable fallback for onsite-preferring users
    if opp_loc == "remote" and "onsite" in preferred:
        return 0.6

    return 0.4