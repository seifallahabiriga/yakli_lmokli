from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.schemas.opportunity import OpportunitySummary


# =============================================================================
# Request schemas
# =============================================================================

class ClusterCreate(BaseModel):
    """Written by AgentCluster — not exposed as a user-facing endpoint."""
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    centroid: list[float] | None = None
    top_keywords: list[str] = Field(default_factory=list)
    dominant_domains: list[str] = Field(default_factory=list)
    algorithm_meta: dict = Field(default_factory=dict)


class ClusterUpdate(BaseModel):
    """Recompute cycle writes updated stats back to the DB."""
    name: str | None = Field(None, max_length=255)
    description: str | None = None
    centroid: list[float] | None = None
    top_keywords: list[str] | None = None
    dominant_domains: list[str] | None = None
    member_count: int | None = Field(None, ge=0)
    avg_relevance_score: float | None = Field(None, ge=0.0, le=1.0)
    algorithm_meta: dict | None = None


# =============================================================================
# Response schemas
# =============================================================================

class ClusterPublic(BaseModel):
    """Full detail — returned by GET /clusters/{id}."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    top_keywords: list[str]
    dominant_domains: list[str]
    member_count: int
    avg_relevance_score: float | None
    algorithm_meta: dict
    created_at: datetime
    last_recomputed_at: datetime


class ClusterWithOpportunities(ClusterPublic):
    """
    Extended detail — includes a page of member opportunities.
    Used by the dashboard cluster explorer.
    """
    opportunities: list[OpportunitySummary] = Field(default_factory=list)


class ClusterSummary(BaseModel):
    """Lightweight — used in opportunity detail and sidebar widgets."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    member_count: int
    top_keywords: list[str]
    dominant_domains: list[str]


class ClusterListResponse(BaseModel):
    items: list[ClusterSummary]
    total: int