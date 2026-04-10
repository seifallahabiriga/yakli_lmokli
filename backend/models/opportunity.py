from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.enums import (
    OpportunityDomain,
    OpportunityLevel,
    OpportunityLocationType,
    OpportunityStatus,
    OpportunityType,
    ScraperType,
)
from db.base import Base


class Opportunity(Base):
    __tablename__ = "opportunities"

    # -------------------------------------------------------------------------
    # Primary key
    # -------------------------------------------------------------------------
    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # -------------------------------------------------------------------------
    # Classification
    # -------------------------------------------------------------------------
    type: Mapped[OpportunityType] = mapped_column(
        Enum(OpportunityType, name="opportunitytype"), nullable=False, index=True
    )
    domain: Mapped[OpportunityDomain] = mapped_column(
        Enum(OpportunityDomain, name="opportunitydomain"),
        nullable=False,
        default=OpportunityDomain.OTHER,
        index=True,
    )
    level: Mapped[OpportunityLevel] = mapped_column(
        Enum(OpportunityLevel, name="opportunitylevel"),
        nullable=False,
        default=OpportunityLevel.ALL,
        index=True,
    )
    status: Mapped[OpportunityStatus] = mapped_column(
        Enum(OpportunityStatus, name="opportunitystatus"),
        nullable=False,
        default=OpportunityStatus.DRAFT,
        index=True,
    )

    # -------------------------------------------------------------------------
    # Content
    # -------------------------------------------------------------------------
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    organization: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source: Mapped[str] = mapped_column(String(255), nullable=False)  # scraper origin
    url: Mapped[str] = mapped_column(String(2048), nullable=False, unique=True)

    # -------------------------------------------------------------------------
    # Location
    # -------------------------------------------------------------------------
    location_type: Mapped[OpportunityLocationType] = mapped_column(
        Enum(OpportunityLocationType, name="opportunitylocationtype"),
        nullable=False,
        default=OpportunityLocationType.UNKNOWN,
    )
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)

    # -------------------------------------------------------------------------
    # Eligibility & requirements
    # Stored as JSONB for maximum flexibility across opportunity types.
    # Example: {"gpa_min": 3.0, "languages": ["English", "French"], "age_max": 35}
    # -------------------------------------------------------------------------
    eligibility: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    required_skills: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, server_default="{}"
    )
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, server_default="{}"
    )

    # -------------------------------------------------------------------------
    # Dates
    # -------------------------------------------------------------------------
    deadline: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    start_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_months: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # -------------------------------------------------------------------------
    # Financial
    # -------------------------------------------------------------------------
    is_paid: Mapped[bool | None] = mapped_column(nullable=True)
    stipend_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    stipend_currency: Mapped[str | None] = mapped_column(String(10), nullable=True)

    # -------------------------------------------------------------------------
    # ML outputs — written by AgentClassifier and AgentCluster
    # -------------------------------------------------------------------------
    embedding: Mapped[list | None] = mapped_column(
        JSONB, nullable=True
        # Stored as JSON array; loaded into numpy/FAISS at recompute time.
        # We don't use pgvector here to avoid an extra extension dependency,
        # but this field is the bridge between the DB and the FAISS index.
    )
    cluster_id: Mapped[int | None] = mapped_column(
        ForeignKey("opportunity_clusters.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    classifier_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Timestamp written by AgentClassifier after embedding is generated.
    classified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Set to True immediately after embedding is written.
    # Cleared to False once AgentCluster assigns a cluster_id.
    # Indexed so the cluster agent can fetch unassigned items with a fast scan
    # instead of checking embedding IS NOT NULL AND cluster_id IS NULL.
    needs_cluster_assignment: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, index=True
    )

    # -------------------------------------------------------------------------
    # Full-text search vector — populated by a Postgres trigger or Alembic migration
    # ts_vector = to_tsvector('english', title || ' ' || description)
    # -------------------------------------------------------------------------
    search_vector: Mapped[str | None] = mapped_column(TSVECTOR, nullable=True)

    # -------------------------------------------------------------------------
    # Scraping metadata
    # -------------------------------------------------------------------------
    scraper_type: Mapped[ScraperType] = mapped_column(
        Enum(ScraperType, name="scrapertype"),
        nullable=False,
        default=ScraperType.STATIC,
    )
    raw_data: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
        # Stores the unprocessed scrape payload for debugging / re-processing.
    )

    # -------------------------------------------------------------------------
    # Timestamps
    # -------------------------------------------------------------------------
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # -------------------------------------------------------------------------
    # Relationships
    # -------------------------------------------------------------------------
    cluster: Mapped["OpportunityCluster | None"] = relationship(  # noqa: F821
        "OpportunityCluster",
        back_populates="opportunities",
        lazy="selectin",
    )
    recommendations: Mapped[list["Recommendation"]] = relationship(  # noqa: F821
        "Recommendation",
        back_populates="opportunity",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    notifications: Mapped[list["Notification"]] = relationship(  # noqa: F821
        "Notification",
        back_populates="opportunity",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<Opportunity id={self.id} type={self.type} "
            f"title={self.title!r} status={self.status}>"
        )