from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.enums import NotificationStatus, NotificationType
from backend.db.base import Base


class Notification(Base):
    __tablename__ = "notifications"

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
    opportunity_id: Mapped[int | None] = mapped_column(
        ForeignKey("opportunities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Null for system notifications not tied to a specific opportunity.",
    )

    # -------------------------------------------------------------------------
    # Content
    # -------------------------------------------------------------------------
    type: Mapped[NotificationType] = mapped_column(
        Enum(NotificationType, name="notificationtype"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)

    # -------------------------------------------------------------------------
    # Extra payload — type-specific data for the frontend to act on.
    # Examples:
    #   NEW_OPPORTUNITY:    {"opportunity_id": 42, "deadline": "2026-05-01"}
    #   DEADLINE_REMINDER:  {"opportunity_id": 42, "days_left": 3}
    #   NEW_RECOMMENDATION: {"recommendation_id": 7, "score": 0.91}
    #   CLUSTER_UPDATE:     {"cluster_id": 2, "new_count": 15}
    # -------------------------------------------------------------------------
    payload: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )

    # -------------------------------------------------------------------------
    # Status & delivery
    # -------------------------------------------------------------------------
    status: Mapped[NotificationStatus] = mapped_column(
        Enum(NotificationStatus, name="notificationstatus"),
        nullable=False,
        default=NotificationStatus.UNREAD,
        index=True,
    )
    is_email_sent: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    # -------------------------------------------------------------------------
    # Timestamps
    # -------------------------------------------------------------------------
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        index=True,
    )
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # -------------------------------------------------------------------------
    # Relationships
    # -------------------------------------------------------------------------
    user: Mapped["User"] = relationship(  # noqa: F821
        "User",
        back_populates="notifications",
        lazy="selectin",
    )
    opportunity: Mapped["Opportunity | None"] = relationship(  # noqa: F821
        "Opportunity",
        back_populates="notifications",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<Notification id={self.id} user={self.user_id} "
            f"type={self.type} status={self.status}>"
        )