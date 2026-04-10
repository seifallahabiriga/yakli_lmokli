from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from core.enums import (
    OpportunityDomain,
    OpportunityLevel,
    OpportunityLocationType,
    OpportunityStatus,
    OpportunityType,
    ScraperType,
)


# =============================================================================
# Shared base
# =============================================================================

class OpportunityBase(BaseModel):
    title: str = Field(..., min_length=3, max_length=512)
    description: str | None = None
    organization: str | None = Field(None, max_length=255)
    source: str = Field(..., max_length=255)
    url: str = Field(..., max_length=2048)

    type: OpportunityType
    domain: OpportunityDomain = OpportunityDomain.OTHER
    level: OpportunityLevel = OpportunityLevel.ALL
    location_type: OpportunityLocationType = OpportunityLocationType.UNKNOWN
    location: str | None = Field(None, max_length=255)
    country: str | None = Field(None, max_length=100)

    eligibility: dict = Field(default_factory=dict)
    required_skills: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

    deadline: datetime | None = None
    start_date: datetime | None = None
    duration_months: int | None = Field(None, ge=1, le=120)

    is_paid: bool | None = None
    stipend_amount: float | None = Field(None, ge=0)
    stipend_currency: str | None = Field(None, max_length=10)

    @field_validator("required_skills", "tags", mode="before")
    @classmethod
    def lowercase_list(cls, v: list[str]) -> list[str]:
        return [item.lower().strip() for item in v if item.strip()]

    @field_validator("url", mode="before")
    @classmethod
    def validate_url(cls, v: str) -> str:
        v = v.strip()
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v


# =============================================================================
# Request schemas
# =============================================================================

class OpportunityCreate(OpportunityBase):
    """
    Used by scraper agents when persisting a newly collected opportunity.
    Status defaults to DRAFT — AgentClassifier promotes it to ACTIVE.
    """
    scraper_type: ScraperType = ScraperType.STATIC
    raw_data: dict = Field(default_factory=dict)


class OpportunityUpdate(BaseModel):
    """All fields optional — PATCH semantics for admin corrections."""
    title: str | None = Field(None, min_length=3, max_length=512)
    description: str | None = None
    organization: str | None = Field(None, max_length=255)
    domain: OpportunityDomain | None = None
    level: OpportunityLevel | None = None
    status: OpportunityStatus | None = None
    location_type: OpportunityLocationType | None = None
    location: str | None = Field(None, max_length=255)
    country: str | None = Field(None, max_length=100)
    eligibility: dict | None = None
    required_skills: list[str] | None = None
    tags: list[str] | None = None
    deadline: datetime | None = None
    start_date: datetime | None = None
    duration_months: int | None = Field(None, ge=1, le=120)
    is_paid: bool | None = None
    stipend_amount: float | None = Field(None, ge=0)
    stipend_currency: str | None = Field(None, max_length=10)


class OpportunityFilter(BaseModel):
    """
    Query parameters for GET /opportunities.
    All fields optional — unset means no filter on that dimension.
    """
    type: OpportunityType | None = None
    domain: OpportunityDomain | None = None
    level: OpportunityLevel | None = None
    status: OpportunityStatus | None = None
    location_type: OpportunityLocationType | None = None
    country: str | None = None
    is_paid: bool | None = None
    cluster_id: int | None = None
    search: str | None = Field(
        None,
        max_length=255,
        description="Full-text search against title and description.",
    )
    deadline_after: datetime | None = None
    deadline_before: datetime | None = None
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)


# =============================================================================
# Response schemas
# =============================================================================

class OpportunityPublic(BaseModel):
    """Full detail view — returned by GET /opportunities/{id}."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None
    organization: str | None
    source: str
    url: str
    type: OpportunityType
    domain: OpportunityDomain
    level: OpportunityLevel
    status: OpportunityStatus
    location_type: OpportunityLocationType
    location: str | None
    country: str | None
    eligibility: dict
    required_skills: list[str]
    tags: list[str]
    deadline: datetime | None
    start_date: datetime | None
    duration_months: int | None
    is_paid: bool | None
    stipend_amount: float | None
    stipend_currency: str | None
    cluster_id: int | None
    classifier_confidence: float | None
    scraped_at: datetime
    created_at: datetime
    updated_at: datetime


class OpportunitySummary(BaseModel):
    """
    Lightweight card view — used in list endpoints and embedded
    inside recommendation and notification responses.
    """
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    organization: str | None
    type: OpportunityType
    domain: OpportunityDomain
    level: OpportunityLevel
    status: OpportunityStatus
    location_type: OpportunityLocationType
    country: str | None
    deadline: datetime | None
    is_paid: bool | None
    url: str
    tags: list[str]
    cluster_id: int | None


class OpportunityListResponse(BaseModel):
    """Paginated list response."""
    items: list[OpportunitySummary]
    total: int
    page: int
    page_size: int
    pages: int