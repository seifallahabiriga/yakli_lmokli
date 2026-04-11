from __future__ import annotations
import logging
from typing import TYPE_CHECKING
import numpy as np
from backend.core.config import get_settings

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)
settings = get_settings()

_encoder = None

def get_encoder():
    global _encoder
    if _encoder is None:
        from sentence_transformers import SentenceTransformer
        logger.info(f"Loading sentence-transformer model: {settings.EMBEDDING_MODEL}")
        _encoder = SentenceTransformer(settings.EMBEDDING_MODEL)
    return _encoder

def build_embedding_text(opp) -> str:
    parts = [
        opp.title,
        opp.title,
        opp.organization or "",
        " ".join(opp.tags or []),
        " ".join(opp.required_skills or []),
        (opp.description or "")[:512],
    ]
    return " ".join(p for p in parts if p).strip()

def embed_opportunity(opportunity_id: int, db: Session) -> dict:
    from sqlalchemy import select
    from backend.core.enums import OpportunityStatus
    from backend.models.opportunity import Opportunity
    from backend.workers.worker_app.ml.clusterer import incremental_cluster_assign

    opp = db.execute(
        select(Opportunity).where(Opportunity.id == opportunity_id)
    ).scalar_one_or_none()

    if opp is None:
        return {"error": f"Opportunity {opportunity_id} not found"}

    encoder = get_encoder()
    text = build_embedding_text(opp)
    embedding: np.ndarray = encoder.encode(
        [text],
        normalize_embeddings=True,
    )[0]

    opp.embedding = embedding.tolist()
    from datetime import UTC, datetime
    opp.classified_at = datetime.now(UTC)
    opp.needs_cluster_assignment = True
    opp.status = OpportunityStatus.ACTIVE
    db.flush()

    incremental_cluster_assign([opp], np.array([embedding]), db)
    return {"opportunity_id": opportunity_id, "embedded": True}
