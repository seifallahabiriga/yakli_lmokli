from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base


class OpportunityCluster(Base):
    __tablename__ = "opportunity_clusters"

    # -------------------------------------------------------------------------
    # Primary key
    # -------------------------------------------------------------------------
    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # -------------------------------------------------------------------------
    # Identity — assigned by AgentCluster
    # -------------------------------------------------------------------------
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # -------------------------------------------------------------------------
    # Cluster geometry
    # centroid: mean embedding vector of all member opportunities (JSONB array)
    # top_keywords: most representative terms extracted from member descriptions
    # dominant_domains: sorted list of OpportunityDomain values in this cluster
    # -------------------------------------------------------------------------
    centroid: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    top_keywords: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, server_default="{}"
    )
    dominant_domains: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, server_default="{}"
    )

    # -------------------------------------------------------------------------
    # FAISS integration
    # faiss_index_id: integer ID used in the FAISS IndexIDMap so we can map
    #   ANN search results back to cluster rows without a DB lookup per result.
    # centroid_version: SHA-1 of the centroid vector — changes on every full
    #   re-cluster so job_runner knows when the FAISS index is stale and must
    #   be rebuilt rather than extended incrementally.
    # -------------------------------------------------------------------------
    faiss_index_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, unique=True,
    )
    centroid_version: Mapped[str | None] = mapped_column(
        String(64), nullable=True,
    )

    # -------------------------------------------------------------------------
    # Stats — updated every recompute cycle by AgentCluster
    # -------------------------------------------------------------------------
    member_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_relevance_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # -------------------------------------------------------------------------
    # Algorithm metadata — useful for audit and tuning
    # Example: {"algorithm": "kmeans", "k": 10, "run_id": "abc123"}
    # -------------------------------------------------------------------------
    algorithm_meta: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )

    # -------------------------------------------------------------------------
    # Timestamps
    # -------------------------------------------------------------------------
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    last_recomputed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # -------------------------------------------------------------------------
    # Relationships
    # -------------------------------------------------------------------------
    opportunities: Mapped[list["Opportunity"]] = relationship(  # noqa: F821
        "Opportunity",
        back_populates="cluster",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<OpportunityCluster id={self.id} name={self.name!r} "
            f"members={self.member_count}>"
        )