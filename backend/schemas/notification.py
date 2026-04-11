from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.core.enums import NotificationStatus, NotificationType
from backend.schemas.opportunity import OpportunitySummary


# =============================================================================
# Request schemas
# =============================================================================

class NotificationCreate(BaseModel):
    """
    Written by AgentNotification — not a user-facing endpoint.
    The agent constructs title, body, and payload per notification type.
    """
    user_id: int
    opportunity_id: int | None = None
    type: NotificationType
    title: str = Field(..., min_length=1, max_length=512)
    body: str | None = None
    payload: dict = Field(default_factory=dict)


class NotificationUpdate(BaseModel):
    """Internal — used by the notification agent to record delivery."""
    is_email_sent: bool | None = None
    sent_at: datetime | None = None


class NotificationStatusUpdate(BaseModel):
    """User-facing — mark a notification as read or archived."""
    status: NotificationStatus


class NotificationBulkStatusUpdate(BaseModel):
    """User-facing — bulk mark-as-read from the notification panel."""
    ids: list[int] = Field(..., min_length=1)
    status: NotificationStatus


# =============================================================================
# Response schemas
# =============================================================================

class NotificationPublic(BaseModel):
    """
    Full detail — returned by GET /notifications/{id}.
    Optionally embeds opportunity summary when opportunity_id is set.
    """
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    opportunity_id: int | None
    type: NotificationType
    title: str
    body: str | None
    payload: dict
    status: NotificationStatus
    is_email_sent: bool
    created_at: datetime
    read_at: datetime | None
    sent_at: datetime | None
    opportunity: OpportunitySummary | None = None


class NotificationSummary(BaseModel):
    """
    Lightweight — used in the notification bell / dropdown.
    No embedded opportunity — frontend fetches detail on click.
    """
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: NotificationType
    title: str
    status: NotificationStatus
    created_at: datetime
    opportunity_id: int | None


class NotificationListResponse(BaseModel):
    """Paginated list for GET /users/me/notifications."""
    items: list[NotificationSummary]
    total: int
    unread_count: int
    page: int
    page_size: int
    pages: int


class NotificationFilter(BaseModel):
    """Query parameters for the notification feed."""
    status: NotificationStatus | None = None
    type: NotificationType | None = None
    page: int = Field(1, ge=1)
    page_size: int = Field(30, ge=1, le=100)