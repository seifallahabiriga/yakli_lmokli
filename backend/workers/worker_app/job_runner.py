"""
Job runner — the agent orchestration layer.

All Celery tasks delegate here. This module owns:
  - Scraper agent dispatch
  - Embedding + classification pipeline
  - Incremental FAISS cluster assignment
  - Full KMeans re-cluster with drift detection
  - Recommendation scoring
  - Notification dispatch
  - FAISS index persistence

Rules:
  - All functions are synchronous (called from sync Celery tasks).
  - DB access via sync SQLAlchemy Session passed in from the task.
  - Redis access via sync Redis client passed in from the task.
  - Heavy ML objects (encoder, FAISS index) are module-level singletons
    loaded once per worker process, not per task call.
  - No async code anywhere in this file.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import numpy as np

from backend.core.config import get_settings

if TYPE_CHECKING:
    from redis import Redis
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)
settings = get_settings()

# =============================================================================
# Module-level ML singletons — loaded once per worker process
# =============================================================================

_encoder = None          # sentence_transformers.SentenceTransformer
_faiss_index = None      # faiss.IndexIDMap wrapping IndexFlatL2
_faiss_id_to_cluster: dict[int, int] = {}   # faiss_index_id → cluster DB id
_faiss_version: str | None = None           # centroid_version of current index


def _get_encoder():
    global _encoder
    if _encoder is None:
        from sentence_transformers import SentenceTransformer
        logger.info("Loading sentence-transformer model: %s", settings.EMBEDDING_MODEL)
        _encoder = SentenceTransformer(settings.EMBEDDING_MODEL)
    return _encoder


def _get_faiss_index():
    """
    Returns the in-memory FAISS index, loading from disk if available.
    Returns None if no index has been built yet (first run).
    """
    global _faiss_index, _faiss_id_to_cluster, _faiss_version

    if _faiss_index is not None:
        return _faiss_index

    index_path = _faiss_index_path()
    meta_path = _faiss_meta_path()

    if os.path.exists(index_path) and os.path.exists(meta_path):
        import faiss
        logger.info("Loading FAISS index from disk: %s", index_path)
        _faiss_index = faiss.read_index(index_path)
        with open(meta_path) as f:
            meta = json.load(f)
        _faiss_id_to_cluster = {int(k): v for k, v in meta["id_map"].items()}
        _faiss_version = meta.get("version")
        logger.info(
            "FAISS index loaded — %d centroids, version %s",
            _faiss_index.ntotal,
            _faiss_version,
        )

    return _faiss_index


def _faiss_index_path() -> str:
    os.makedirs(settings.FAISS_INDEX_PATH, exist_ok=True)
    return os.path.join(settings.FAISS_INDEX_PATH, "clusters.index")


def _faiss_meta_path() -> str:
    return os.path.join(settings.FAISS_INDEX_PATH, "clusters_meta.json")


def _centroid_version(centroid: list[float]) -> str:
    """SHA-1 of the centroid vector bytes — used to detect stale FAISS index."""
    return hashlib.sha1(
        np.array(centroid, dtype=np.float32).tobytes()
    ).hexdigest()[:16]


# =============================================================================
# Scraper agents
# =============================================================================

def run_scraper_agent(agent_type: str, db: Session, cache: Redis) -> dict:
    """
    Dispatches the correct observer agent based on agent_type string.
    Each agent scrapes its sources, deduplicates against the DB by URL,
    and inserts new opportunities with status=DRAFT.

    Returns a summary dict for Celery task result storage.
    """
    from backend.core.enums import OpportunityStatus, OpportunityType, ScraperType
    from backend.models.opportunity import Opportunity

    agent_map = {
        "internship": _scrape_internships,
        "scholarship": _scrape_scholarships,
        "project": _scrape_projects,
        "certification": _scrape_certifications,
        "postdoc": _scrape_postdocs,
    }

    scrape_fn = agent_map.get(agent_type)
    if scrape_fn is None:
        raise ValueError(f"Unknown agent type: {agent_type}")

    logger.info("Scraper agent starting: %s", agent_type)
    raw_items = scrape_fn()
    logger.info("Scraper agent %s collected %d raw items", agent_type, len(raw_items))

    inserted = 0
    skipped = 0

    for item in raw_items:
        url = item.get("url", "").strip()
        if not url:
            skipped += 1
            continue

        # Deduplication — skip if URL already in DB
        existing = db.execute(
            __import__("sqlalchemy").select(Opportunity.id).where(
                Opportunity.url == url
            )
        ).scalar_one_or_none()

        if existing is not None:
            skipped += 1
            continue

        opportunity = Opportunity(
            title=item.get("title", "Untitled")[:512],
            description=item.get("description"),
            organization=item.get("organization"),
            source=item.get("source", agent_type),
            url=url,
            type=item.get("type", OpportunityType.INTERNSHIP),
            domain=item.get("domain", "other"),
            level=item.get("level", "all"),
            location_type=item.get("location_type", "unknown"),
            location=item.get("location"),
            country=item.get("country"),
            eligibility=item.get("eligibility", {}),
            required_skills=item.get("required_skills", []),
            tags=item.get("tags", []),
            deadline=item.get("deadline"),
            start_date=item.get("start_date"),
            duration_months=item.get("duration_months"),
            is_paid=item.get("is_paid"),
            stipend_amount=item.get("stipend_amount"),
            stipend_currency=item.get("stipend_currency"),
            status=OpportunityStatus.DRAFT,
            scraper_type=item.get("scraper_type", ScraperType.STATIC),
            raw_data=item,
        )
        db.add(opportunity)
        inserted += 1

    logger.info(
        "Scraper agent %s done — inserted: %d, skipped: %d",
        agent_type, inserted, skipped,
    )
    return {"agent": agent_type, "inserted": inserted, "skipped": skipped}


# ---------------------------------------------------------------------------
# Individual scraper implementations
# Each returns a list of raw dicts. Scraping logic (BS4 / Playwright) lives
# here and will be expanded per-source. Stubs are provided so the pipeline
# runs end-to-end before all sources are implemented.
# ---------------------------------------------------------------------------

def _scrape_internships() -> list[dict]:
    """
    Sources: LinkedIn, Indeed, Glassdoor, university portals.
    Uses Playwright for JS-rendered job boards, BS4 for static portals.
    """
    from backend.workers.worker_app.scrapers.internship_scraper import InternshipScraper
    return InternshipScraper().run()


def _scrape_scholarships() -> list[dict]:
    from backend.workers.worker_app.scrapers.scholarship_scraper import ScholarshipScraper
    return ScholarshipScraper().run()


def _scrape_projects() -> list[dict]:
    from backend.workers.worker_app.scrapers.project_scraper import ProjectScraper
    return ProjectScraper().run()


def _scrape_certifications() -> list[dict]:
    from backend.workers.worker_app.scrapers.certification_scraper import CertificationScraper
    return CertificationScraper().run()


def _scrape_postdocs() -> list[dict]:
    from backend.workers.worker_app.scrapers.postdoc_scraper import PostdocScraper
    return PostdocScraper().run()


# =============================================================================
# Classifier agent — embedding + NLP tagging
# =============================================================================

def run_classifier_agent(db: Session, cache: Redis) -> dict:
    """
    1. Loads all DRAFT opportunities without embeddings.
    2. Generates sentence-transformer embeddings in batch.
    3. Runs spaCy NER + keyword extraction to enrich tags.
    4. Writes embeddings back, sets needs_cluster_assignment=True,
       promotes status to ACTIVE, records classified_at.
    5. Attempts incremental FAISS cluster assignment for newly embedded items.
    """
    from sqlalchemy import select
    from backend.core.enums import OpportunityStatus
    from backend.models.opportunity import Opportunity

    # Load unembedded drafts
    rows = db.execute(
        select(Opportunity).where(Opportunity.embedding.is_(None))
    ).scalars().all()

    if not rows:
        logger.info("Classifier: no unembedded opportunities found")
        return {"embedded": 0, "assigned": 0}

    logger.info("Classifier: embedding %d opportunities", len(rows))

    encoder = _get_encoder()
    texts = [_build_embedding_text(opp) for opp in rows]

    # Batch encode — sentence-transformers handles batching internally
    embeddings: np.ndarray = encoder.encode(
        texts,
        batch_size=32,
        show_progress_bar=False,
        normalize_embeddings=True,   # L2-normalize for cosine similarity via dot product
    )

    now = datetime.now(UTC)

    for opp, embedding in zip(rows, embeddings):
        opp.embedding = embedding.tolist()
        opp.classified_at = now
        opp.needs_cluster_assignment = True
        opp.status = OpportunityStatus.ACTIVE

        # NLP enrichment — extract additional tags
        extra_tags = _extract_tags(opp.title, opp.description or "")
        if extra_tags:
            existing = set(opp.tags or [])
            opp.tags = list(existing | extra_tags)

    db.flush()

    # Attempt incremental cluster assignment for all newly embedded items
    assigned = _incremental_cluster_assign(rows, embeddings, db)

    logger.info(
        "Classifier done — embedded: %d, cluster-assigned: %d",
        len(rows), assigned,
    )
    return {"embedded": len(rows), "assigned": assigned}


def embed_opportunity(opportunity_id: int, db: Session) -> dict:
    """
    Embeds a single opportunity by ID.
    Called immediately after a scraper saves a new item (via producer).
    """
    from sqlalchemy import select
    from backend.core.enums import OpportunityStatus
    from backend.models.opportunity import Opportunity

    opp = db.execute(
        select(Opportunity).where(Opportunity.id == opportunity_id)
    ).scalar_one_or_none()

    if opp is None:
        return {"error": f"Opportunity {opportunity_id} not found"}

    encoder = _get_encoder()
    text = _build_embedding_text(opp)
    embedding: np.ndarray = encoder.encode(
        [text],
        normalize_embeddings=True,
    )[0]

    opp.embedding = embedding.tolist()
    opp.classified_at = datetime.now(UTC)
    opp.needs_cluster_assignment = True
    opp.status = OpportunityStatus.ACTIVE
    db.flush()

    _incremental_cluster_assign([opp], np.array([embedding]), db)
    return {"opportunity_id": opportunity_id, "embedded": True}


def _build_embedding_text(opp) -> str:
    """
    Constructs the text passed to the sentence-transformer.
    Combines the most semantically rich fields — title carries the most
    signal so it's repeated to upweight it.
    """
    parts = [
        opp.title,
        opp.title,   # intentional repeat — upweights title in embedding space
        opp.organization or "",
        " ".join(opp.tags or []),
        " ".join(opp.required_skills or []),
        (opp.description or "")[:512],   # truncate long descriptions
    ]
    return " ".join(p for p in parts if p).strip()


def _extract_tags(title: str, description: str) -> set[str]:
    """
    Uses spaCy to extract named entities and domain keywords from text.
    Returns a set of lowercase tags to merge into the opportunity's tag list.
    """
    try:
        import spacy
        nlp = spacy.load(settings.SPACY_MODEL)
        doc = nlp(f"{title}. {description[:1000]}")

        tags: set[str] = set()

        # Named entities: ORG, GPE (location), PRODUCT
        for ent in doc.ents:
            if ent.label_ in ("ORG", "GPE", "PRODUCT"):
                tags.add(ent.text.lower().strip())

        # Noun chunks as domain keywords (filter short/stopword-only chunks)
        for chunk in doc.noun_chunks:
            token = chunk.root
            if not token.is_stop and not token.is_punct and len(chunk.text) > 3:
                tags.add(chunk.text.lower().strip())

        return tags
    except Exception as exc:
        logger.warning("spaCy tag extraction failed: %s", exc)
        return set()


# =============================================================================
# Cluster agent — KMeans + incremental FAISS assignment
# =============================================================================

DRIFT_THRESHOLD = 0.10   # trigger full re-cluster if >10% of embedded items unassigned


def run_cluster_agent(db: Session, cache: Redis) -> dict:
    """
    Decides between incremental FAISS assignment and full KMeans re-cluster
    based on the drift threshold, then updates cluster memberships in the DB.
    """
    from sqlalchemy import func, select
    from backend.models.opportunity import Opportunity

    # Count totals for drift check
    total_embedded = db.execute(
        select(func.count()).select_from(Opportunity).where(
            Opportunity.embedding.is_not(None)
        )
    ).scalar_one()

    total_unassigned = db.execute(
        select(func.count()).select_from(Opportunity).where(
            Opportunity.needs_cluster_assignment.is_(True)
        )
    ).scalar_one()

    if total_embedded == 0:
        logger.info("Cluster agent: no embedded opportunities yet")
        return {"action": "skip", "reason": "no_embeddings"}

    drift_ratio = total_unassigned / total_embedded
    logger.info(
        "Cluster agent: %d unassigned / %d total (drift=%.2f%%)",
        total_unassigned, total_embedded, drift_ratio * 100,
    )

    faiss_idx = _get_faiss_index()

    if faiss_idx is None or drift_ratio > DRIFT_THRESHOLD:
        # Full re-cluster
        return _full_recluster(db, cache)
    else:
        # Incremental assignment only
        unassigned_opps = db.execute(
            select(Opportunity).where(
                Opportunity.needs_cluster_assignment.is_(True)
            )
        ).scalars().all()

        embeddings = np.array(
            [opp.embedding for opp in unassigned_opps], dtype=np.float32
        )
        assigned = _incremental_cluster_assign(unassigned_opps, embeddings, db)
        _update_cluster_stats(db)
        _invalidate_cluster_cache(cache)
        return {"action": "incremental", "assigned": assigned}


def _full_recluster(db: Session, cache: Redis) -> dict:
    """
    Full KMeans re-cluster of all embedded opportunities.
    Steps:
      1. Load all embeddings from DB.
      2. Run KMeans with k from config.
      3. Wipe existing clusters, create new ones.
      4. Assign all opportunities to their nearest centroid.
      5. Rebuild FAISS index from new centroids.
      6. Invalidate Redis cluster cache.
    """
    global _faiss_index, _faiss_id_to_cluster, _faiss_version

    import faiss
    from sklearn.cluster import KMeans
    from sqlalchemy import delete, select, update
    from backend.models.cluster import OpportunityCluster
    from backend.models.opportunity import Opportunity

    logger.info("Full re-cluster starting")

    # 1. Load all embeddings
    rows = db.execute(
        select(Opportunity).where(Opportunity.embedding.is_not(None))
    ).scalars().all()

    if len(rows) < settings.CLUSTER_N_CLUSTERS:
        logger.warning(
            "Not enough opportunities (%d) to form %d clusters — skipping",
            len(rows), settings.CLUSTER_N_CLUSTERS,
        )
        return {"action": "skip", "reason": "insufficient_data", "count": len(rows)}

    embeddings = np.array([row.embedding for row in rows], dtype=np.float32)
    opp_ids = [row.id for row in rows]

    # 2. KMeans
    k = min(settings.CLUSTER_N_CLUSTERS, len(rows))
    logger.info("Running KMeans k=%d on %d embeddings", k, len(rows))
    kmeans = KMeans(n_clusters=k, random_state=42, n_init="auto")
    labels: np.ndarray = kmeans.fit_predict(embeddings)
    centroids: np.ndarray = kmeans.cluster_centers_.astype(np.float32)

    # 3. Wipe old clusters — FK SET NULL handles opportunity.cluster_id
    db.execute(delete(OpportunityCluster))
    db.flush()

    # 4. Create new clusters
    dim = centroids.shape[1]
    new_clusters: list[OpportunityCluster] = []

    for cluster_idx in range(k):
        centroid = centroids[cluster_idx].tolist()
        member_mask = labels == cluster_idx
        member_opps = [rows[i] for i in range(len(rows)) if member_mask[i]]
        member_embeddings = embeddings[member_mask]

        keywords = _extract_cluster_keywords(member_opps)
        domains = _dominant_domains(member_opps)
        version = _centroid_version(centroid)

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

    db.flush()   # assigns cluster IDs

    # 5. Assign opportunities to clusters + clear flag
    for i, opp in enumerate(rows):
        cluster = new_clusters[labels[i]]
        opp.cluster_id = cluster.id
        opp.needs_cluster_assignment = False

    db.flush()

    # 6. Rebuild FAISS index
    index_flat = faiss.IndexFlatIP(dim)   # Inner product on normalized vectors = cosine sim
    index = faiss.IndexIDMap(index_flat)
    faiss_ids = np.array([c.faiss_index_id for c in new_clusters], dtype=np.int64)
    index.add_with_ids(centroids, faiss_ids)

    _faiss_index = index
    _faiss_id_to_cluster = {c.faiss_index_id: c.id for c in new_clusters}
    _faiss_version = new_clusters[0].centroid_version if new_clusters else None

    _update_cluster_stats(db)
    _invalidate_cluster_cache(cache)

    logger.info("Full re-cluster complete — %d clusters created", k)
    return {
        "action": "full_recluster",
        "clusters": k,
        "opportunities": len(rows),
    }


def _incremental_cluster_assign(
    opps: list,
    embeddings: np.ndarray,
    db: Session,
) -> int:
    """
    Assigns each opportunity to its nearest centroid via FAISS ANN search.
    Only runs if a FAISS index exists. Returns count of assigned opportunities.
    """
    faiss_idx = _get_faiss_index()
    if faiss_idx is None or faiss_idx.ntotal == 0 or len(opps) == 0:
        return 0

    query = embeddings.astype(np.float32)
    if query.ndim == 1:
        query = query.reshape(1, -1)

    # Search for nearest centroid (k=1)
    _, faiss_ids = faiss_idx.search(query, 1)   # shape: (n, 1)

    assigned = 0
    for opp, result_ids in zip(opps, faiss_ids):
        faiss_id = int(result_ids[0])
        cluster_db_id = _faiss_id_to_cluster.get(faiss_id)
        if cluster_db_id is not None:
            opp.cluster_id = cluster_db_id
            opp.needs_cluster_assignment = False
            assigned += 1

    return assigned


def _extract_cluster_keywords(opps: list, top_n: int = 10) -> list[str]:
    """
    Extracts the most frequent non-stopword terms across a cluster's opportunities.
    Used to auto-name / describe clusters.
    """
    from collections import Counter
    import re

    stopwords = {
        "the", "and", "for", "with", "this", "that", "are", "from",
        "will", "have", "has", "been", "you", "your", "our", "their",
        "can", "may", "also", "other", "any", "all", "not", "but",
    }
    counter: Counter = Counter()
    for opp in opps:
        text = f"{opp.title} {' '.join(opp.tags or [])} {' '.join(opp.required_skills or [])}"
        words = re.findall(r"\b[a-z]{3,}\b", text.lower())
        counter.update(w for w in words if w not in stopwords)

    return [word for word, _ in counter.most_common(top_n)]


def _dominant_domains(opps: list) -> list[str]:
    """Returns domains sorted by frequency within a cluster."""
    from collections import Counter
    counter: Counter = Counter(
        opp.domain.value if hasattr(opp.domain, "value") else str(opp.domain)
        for opp in opps
    )
    return [domain for domain, _ in counter.most_common()]


def _update_cluster_stats(db: Session) -> None:
    """Refreshes member_count for all clusters after any assignment change."""
    from sqlalchemy import func, select, update
    from backend.models.cluster import OpportunityCluster
    from backend.models.opportunity import Opportunity

    counts = db.execute(
        select(Opportunity.cluster_id, func.count().label("cnt"))
        .where(Opportunity.cluster_id.is_not(None))
        .group_by(Opportunity.cluster_id)
    ).all()

    for row in counts:
        db.execute(
            update(OpportunityCluster)
            .where(OpportunityCluster.id == row.cluster_id)
            .values(member_count=row.cnt)
        )
    db.flush()


def _invalidate_cluster_cache(cache: Redis) -> None:
    """Deletes all cluster-related Redis cache keys after a recompute."""
    from backend.queue.redis_client import CacheKeys
    keys = cache.keys("clusters:*")
    if keys:
        cache.delete(*keys)


# =============================================================================
# FAISS index persistence
# =============================================================================

def save_faiss_index() -> dict:
    """
    Serializes the in-memory FAISS index and metadata to disk.
    Called by the persist_faiss_index Celery task every hour.
    """
    import faiss

    faiss_idx = _get_faiss_index()
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

    logger.info("FAISS index saved to %s (%d centroids)", index_path, faiss_idx.ntotal)
    return {"saved": True, "path": index_path, "centroids": faiss_idx.ntotal}


# =============================================================================
# Recommendation agent
# =============================================================================

def run_recommendation_agent(
    db: Session,
    cache: Redis,
    user_id: int | None = None,
) -> dict:
    """
    Scores opportunities against user profiles using a multi-signal approach:
      - Semantic similarity (FAISS ANN on user profile embedding)
      - Skill overlap (Jaccard)
      - Domain match
      - Level match
      - Deadline proximity
      - Location preference

    user_id=None → process all active users.
    user_id=N    → process single user (profile update trigger).
    """
    from sqlalchemy import select
    from backend.models.user import User
    from backend.models.opportunity import Opportunity
    from backend.models.recommendation import Recommendation
    from backend.core.enums import OpportunityStatus, RecommendationStatus

    # Load users to process
    user_query = select(User).where(User.is_active.is_(True))
    if user_id is not None:
        user_query = user_query.where(User.id == user_id)
    users = db.execute(user_query).scalars().all()

    if not users:
        return {"users_processed": 0, "recommendations_created": 0}

    # Load all active opportunities with embeddings
    active_opps = db.execute(
        select(Opportunity).where(
            Opportunity.status == OpportunityStatus.ACTIVE,
            Opportunity.embedding.is_not(None),
        )
    ).scalars().all()

    if not active_opps:
        return {"users_processed": len(users), "recommendations_created": 0}

    opp_embeddings = np.array(
        [opp.embedding for opp in active_opps], dtype=np.float32
    )

    encoder = _get_encoder()
    total_created = 0
    now = datetime.now(UTC)

    for user in users:
        # Build user profile embedding from interests + skills + field
        profile_text = _build_user_profile_text(user)
        profile_embedding: np.ndarray = encoder.encode(
            [profile_text], normalize_embeddings=True
        )[0]

        # Cosine similarity via dot product (embeddings are L2-normalized)
        similarities = opp_embeddings @ profile_embedding   # shape: (n_opps,)

        for i, opp in enumerate(active_opps):
            score, breakdown = _score_opportunity(
                user=user,
                opp=opp,
                semantic_sim=float(similarities[i]),
                now=now,
            )

            # Skip low-relevance opportunities
            if score < 0.2:
                continue

            # Upsert recommendation
            existing = db.execute(
                select(Recommendation).where(
                    Recommendation.user_id == user.id,
                    Recommendation.opportunity_id == opp.id,
                )
            ).scalar_one_or_none()

            if existing is None:
                rec = Recommendation(
                    user_id=user.id,
                    opportunity_id=opp.id,
                    score=score,
                    score_breakdown=breakdown,
                    status=RecommendationStatus.SCORED,
                    scored_at=now,
                )
                db.add(rec)
                total_created += 1
            else:
                # Update score if it changed significantly
                if abs(existing.score - score) > 0.05:
                    existing.score = score
                    existing.score_breakdown = breakdown
                    existing.scored_at = now

        # Re-rank this user's recommendations by score
        user_recs = db.execute(
            select(Recommendation)
            .where(
                Recommendation.user_id == user.id,
                Recommendation.status == RecommendationStatus.SCORED,
            )
            .order_by(Recommendation.score.desc())
        ).scalars().all()

        for rank, rec in enumerate(user_recs, start=1):
            rec.rank = rank

        # Invalidate user recommendation cache
        cache.delete(f"recommendations:user:{user.id}")

    db.flush()
    logger.info(
        "Recommendation agent done — users: %d, created: %d",
        len(users), total_created,
    )
    return {"users_processed": len(users), "recommendations_created": total_created}


def _build_user_profile_text(user) -> str:
    parts = [
        user.field_of_study or "",
        " ".join(user.interests or []),
        " ".join(user.skills or []),
        user.bio or "",
    ]
    return " ".join(p for p in parts if p).strip() or "general student"


def _score_opportunity(
    user,
    opp,
    semantic_sim: float,
    now: datetime,
) -> tuple[float, dict]:
    """
    Computes a composite relevance score in [0, 1].
    Returns (score, breakdown_dict).
    """
    breakdown: dict[str, float] = {}

    # 1. Semantic similarity (0–1, already computed via cosine)
    breakdown["semantic_similarity"] = round(max(0.0, float(semantic_sim)), 4)

    # 2. Skill overlap — Jaccard between user skills and opportunity required_skills
    user_skills = set(s.lower() for s in (user.skills or []))
    opp_skills = set(s.lower() for s in (opp.required_skills or []))
    if opp_skills:
        overlap = len(user_skills & opp_skills) / len(user_skills | opp_skills)
    else:
        overlap = 0.5   # no required skills = open to all
    breakdown["skill_overlap"] = round(overlap, 4)

    # 3. Domain match
    user_interests = set(i.lower() for i in (user.interests or []))
    opp_domain = opp.domain.value if hasattr(opp.domain, "value") else str(opp.domain)
    domain_match = 1.0 if opp_domain in user_interests else 0.3
    breakdown["domain_match"] = domain_match

    # 4. Level match
    user_level = user.academic_level.value if user.academic_level else None
    opp_level = opp.level.value if hasattr(opp.level, "value") else str(opp.level)
    if opp_level == "all" or user_level is None:
        level_match = 0.8
    elif opp_level == user_level:
        level_match = 1.0
    else:
        level_match = 0.2
    breakdown["level_match"] = level_match

    # 5. Deadline proximity — higher score for deadlines 2–8 weeks away
    if opp.deadline:
        days_left = (opp.deadline - now).days
        if days_left < 0:
            deadline_score = 0.0
        elif days_left <= 14:
            deadline_score = 1.0   # urgent
        elif days_left <= 60:
            deadline_score = 0.8
        elif days_left <= 120:
            deadline_score = 0.5
        else:
            deadline_score = 0.3
    else:
        deadline_score = 0.5   # no deadline = rolling, treat as medium
    breakdown["deadline_proximity"] = deadline_score

    # 6. Location preference (from user.preferences)
    preferred_locations = user.preferences.get("locations", [])
    opp_loc_type = opp.location_type.value if hasattr(opp.location_type, "value") else ""
    if not preferred_locations:
        location_score = 0.7
    elif opp_loc_type in preferred_locations or "remote" in preferred_locations and opp_loc_type == "remote":
        location_score = 1.0
    else:
        location_score = 0.4
    breakdown["location_preference"] = location_score

    # Weighted composite
    weights = {
        "semantic_similarity": 0.35,
        "skill_overlap": 0.25,
        "domain_match": 0.15,
        "level_match": 0.10,
        "deadline_proximity": 0.08,
        "location_preference": 0.07,
    }

    score = sum(breakdown[k] * w for k, w in weights.items())
    return round(score, 4), breakdown


# =============================================================================
# Notification agents
# =============================================================================

def run_deadline_reminder_agent(
    db: Session,
    cache: Redis,
    within_days: int = 3,
) -> dict:
    """
    Creates deadline reminder notifications for users who have SCORED
    recommendations on opportunities expiring within `within_days`.
    Skips if a reminder for the same opportunity was already sent.
    """
    from sqlalchemy import and_, select
    from backend.models.notification import Notification
    from backend.models.opportunity import Opportunity
    from backend.models.recommendation import Recommendation
    from backend.core.enums import (
        NotificationStatus, NotificationType,
        OpportunityStatus, RecommendationStatus,
    )
    from datetime import timedelta

    cutoff = datetime.now(UTC) + timedelta(days=within_days)
    now = datetime.now(UTC)

    expiring = db.execute(
        select(Opportunity).where(
            and_(
                Opportunity.status == OpportunityStatus.ACTIVE,
                Opportunity.deadline >= now,
                Opportunity.deadline <= cutoff,
            )
        )
    ).scalars().all()

    created = 0
    for opp in expiring:
        # Find users with scored recommendations for this opportunity
        recs = db.execute(
            select(Recommendation).where(
                and_(
                    Recommendation.opportunity_id == opp.id,
                    Recommendation.status == RecommendationStatus.SCORED,
                )
            )
        ).scalars().all()

        for rec in recs:
            # Skip if reminder already sent
            already_sent = db.execute(
                select(Notification.id).where(
                    and_(
                        Notification.user_id == rec.user_id,
                        Notification.opportunity_id == opp.id,
                        Notification.type == NotificationType.DEADLINE_REMINDER,
                    )
                )
            ).scalar_one_or_none()

            if already_sent:
                continue

            days_left = (opp.deadline - now).days
            notification = Notification(
                user_id=rec.user_id,
                opportunity_id=opp.id,
                type=NotificationType.DEADLINE_REMINDER,
                title=f"Deadline in {days_left} day{'s' if days_left != 1 else ''}: {opp.title[:80]}",
                body=f"The application deadline for '{opp.title}' is approaching.",
                payload={
                    "opportunity_id": opp.id,
                    "days_left": days_left,
                    "deadline": opp.deadline.isoformat() if opp.deadline else None,
                },
                status=NotificationStatus.UNREAD,
            )
            db.add(notification)
            created += 1

    db.flush()
    logger.info("Deadline reminder agent: created %d notifications", created)
    return {"notifications_created": created}


def run_new_opportunity_notifier(
    opportunity_id: int,
    db: Session,
    cache: Redis,
) -> dict:
    """
    Notifies users whose skills/interests overlap with a newly published opportunity.
    Called after a scraper agent promotes an opportunity to ACTIVE.
    """
    from sqlalchemy import select
    from backend.models.notification import Notification
    from backend.models.opportunity import Opportunity
    from backend.models.user import User
    from backend.core.enums import NotificationStatus, NotificationType

    opp = db.execute(
        select(Opportunity).where(Opportunity.id == opportunity_id)
    ).scalar_one_or_none()

    if opp is None:
        return {"error": f"Opportunity {opportunity_id} not found"}

    opp_skills = set(s.lower() for s in (opp.required_skills or []))
    opp_tags = set(t.lower() for t in (opp.tags or []))
    opp_domain = opp.domain.value if hasattr(opp.domain, "value") else str(opp.domain)

    users = db.execute(
        select(User).where(User.is_active.is_(True))
    ).scalars().all()

    created = 0
    for user in users:
        user_skills = set(s.lower() for s in (user.skills or []))
        user_interests = set(i.lower() for i in (user.interests or []))

        skill_overlap = bool(user_skills & opp_skills)
        interest_match = opp_domain in user_interests or bool(user_interests & opp_tags)

        if not (skill_overlap or interest_match):
            continue

        # Dedup check
        already_sent = db.execute(
            __import__("sqlalchemy").select(Notification.id).where(
                Notification.user_id == user.id,
                Notification.opportunity_id == opp.id,
                Notification.type == NotificationType.NEW_OPPORTUNITY,
            )
        ).scalar_one_or_none()

        if already_sent:
            continue

        notification = Notification(
            user_id=user.id,
            opportunity_id=opp.id,
            type=NotificationType.NEW_OPPORTUNITY,
            title=f"New opportunity: {opp.title[:80]}",
            body=f"A new {opp.type.value} matching your profile was just published.",
            payload={"opportunity_id": opp.id, "type": opp.type.value},
            status=NotificationStatus.UNREAD,
        )
        db.add(notification)
        created += 1

    db.flush()
    logger.info(
        "New opportunity notifier: opportunity=%d, notifications=%d",
        opportunity_id, created,
    )
    return {"opportunity_id": opportunity_id, "notifications_created": created}


def run_recommendation_notifier(
    user_id: int,
    recommendation_id: int,
    db: Session,
    cache: Redis,
) -> dict:
    from sqlalchemy import select
    from backend.models.notification import Notification
    from backend.models.recommendation import Recommendation
    from backend.core.enums import NotificationStatus, NotificationType

    rec = db.execute(
        select(Recommendation).where(Recommendation.id == recommendation_id)
    ).scalar_one_or_none()

    if rec is None:
        return {"error": f"Recommendation {recommendation_id} not found"}

    notification = Notification(
        user_id=user_id,
        opportunity_id=rec.opportunity_id,
        type=NotificationType.NEW_RECOMMENDATION,
        title="New recommendation for you",
        body=f"We found an opportunity matching your profile with a relevance score of {rec.score:.0%}.",
        payload={
            "recommendation_id": recommendation_id,
            "opportunity_id": rec.opportunity_id,
            "score": rec.score,
        },
        status=NotificationStatus.UNREAD,
    )
    db.add(notification)
    db.flush()
    return {"notification_created": True, "recommendation_id": recommendation_id}