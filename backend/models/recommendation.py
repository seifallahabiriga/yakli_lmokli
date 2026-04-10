from datetime import UTC, datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.enums import RecommendationStatus
from db.base import Base


class Recommendation(Base):
    __tablename__ = "recommendations"

    # One user should never have duplicate recommendations for the same opportunity.
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "opportunity_id",
            name="uq_recommendations_user_opportunity",
        ),
    )

    # -------------------------------------------------------------------------
    # Primary key
    # -------------------------------------------------------------------------
    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # -------------------------------------------------------------------------
    # Foreign keys
    # -------------------------------------------------------------------------
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    opportunity_id: Mapped[int] = mapped_column(
        ForeignKey("opportunities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # -------------------------------------------------------------------------
    # Scoring — produced by AgentRelevanceMatcher / AgentAdvisor
    # -------------------------------------------------------------------------
    score: Mapped[float] = mapped_column(Float, nullable=False)
    rank: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Position in the user's ranked recommendation list (1 = best).",
    )

    # -------------------------------------------------------------------------
    # Score breakdown — JSONB for auditability and future UI display
    # Example:
    # {
    #   "skill_overlap": 0.85,
    #   "domain_match": 1.0,
    #   "level_match": 1.0,
    #   "deadline_proximity": 0.6,
    #   "location_preference": 0.5,
    #   "semantic_similarity": 0.78
    # }
    # -------------------------------------------------------------------------
    score_breakdown: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )

    # -------------------------------------------------------------------------
    # LLM-generated explanation — produced by AgentAdvisor via Gemini/Groq
    # Shown to the user as a human-readable reason for the recommendation.
    # -------------------------------------------------------------------------
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)

    # -------------------------------------------------------------------------
    # Status
    # -------------------------------------------------------------------------
    status: Mapped[RecommendationStatus] = mapped_column(
        Enum(RecommendationStatus, name="recommendationstatus"),
        nullable=False,
        default=RecommendationStatus.PENDING,
        index=True,
    )

    # -------------------------------------------------------------------------
    # Timestamps
    # -------------------------------------------------------------------------
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    scored_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    viewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # -------------------------------------------------------------------------
    # Relationships
    # -------------------------------------------------------------------------
    user: Mapped["User"] = relationship(  # noqa: F821
        "User",
        back_populates="recommendations",
        lazy="selectin",
    )
    opportunity: Mapped["Opportunity"] = relationship(  # noqa: F821
        "Opportunity",
        back_populates="recommendations",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<Recommendation id={self.id} user={self.user_id} "
            f"opportunity={self.opportunity_id} score={self.score:.3f}>"
        )