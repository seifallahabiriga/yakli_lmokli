from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from core.enums import RecommendationStatus
from schemas.opportunity import OpportunitySummary
from schemas.user import UserSummary


# =============================================================================
# Request schemas
# =============================================================================

class RecommendationCreate(BaseModel):
    """
    Written by AgentRelevanceMatcher — not a user-facing endpoint.
    user_id and opportunity_id are passed as path/body by the agent task.
    """
    user_id: int
    opportunity_id: int
    score: float = Field(..., ge=0.0, le=1.0)
    score_breakdown: dict = Field(default_factory=dict)
    explanation: str | None = None


class RecommendationUpdate(BaseModel):
    """
    AgentAdvisor updates rank and explanation after initial scoring.
    Users update status (dismiss / mark applied) via PATCH /recommendations/{id}.
    """
    rank: int | None = Field(None, ge=1)
    score: float | None = Field(None, ge=0.0, le=1.0)
    score_breakdown: dict | None = None
    explanation: str | None = None
    status: RecommendationStatus | None = None


class RecommendationStatusUpdate(BaseModel):
    """Minimal update — user-facing status change only."""
    status: RecommendationStatus


# =============================================================================
# Response schemas
# =============================================================================

class RecommendationPublic(BaseModel):
    """
    Full detail — returned by GET /recommendations/{id}.
    Embeds opportunity summary so the frontend never needs a second request.
    """
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    opportunity_id: int
    score: float
    rank: int | None
    score_breakdown: dict
    explanation: str | None
    status: RecommendationStatus
    created_at: datetime
    scored_at: datetime | None
    viewed_at: datetime | None
    opportunity: OpportunitySummary


class RecommendationWithUser(RecommendationPublic):
    """Admin view — includes user summary alongside opportunity."""
    user: UserSummary


class RecommendationSummary(BaseModel):
    """
    Lightweight card — used in the dashboard recommendation feed.
    Avoids loading full opportunity detail for list views.
    """
    model_config = ConfigDict(from_attributes=True)

    id: int
    score: float
    rank: int | None
    status: RecommendationStatus
    explanation: str | None
    created_at: datetime
    opportunity: OpportunitySummary


class RecommendationListResponse(BaseModel):
    """Paginated list for GET /users/me/recommendations."""
    items: list[RecommendationSummary]
    total: int
    page: int
    page_size: int
    pages: int


class RecommendationFilter(BaseModel):
    """Query parameters for filtering a user's recommendation feed."""
    status: RecommendationStatus | None = None
    min_score: float | None = Field(None, ge=0.0, le=1.0)
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)