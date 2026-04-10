from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Enum, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.enums import AcademicLevel, UserRole
from db.base import Base


class User(Base):
    __tablename__ = "users"

    # -------------------------------------------------------------------------
    # Primary key
    # -------------------------------------------------------------------------
    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # -------------------------------------------------------------------------
    # Identity
    # -------------------------------------------------------------------------
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    # -------------------------------------------------------------------------
    # Role & access
    # -------------------------------------------------------------------------
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="userrole"), nullable=False, default=UserRole.STUDENT
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # -------------------------------------------------------------------------
    # Academic profile
    # -------------------------------------------------------------------------
    academic_level: Mapped[AcademicLevel | None] = mapped_column(
        Enum(AcademicLevel, name="academiclevel"), nullable=True
    )
    institution: Mapped[str | None] = mapped_column(String(255), nullable=True)
    field_of_study: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)

    # -------------------------------------------------------------------------
    # Interests & skills
    # Stored as Postgres arrays for efficient overlap queries:
    #   SELECT * FROM users WHERE skills && ARRAY['python', 'nlp']
    # -------------------------------------------------------------------------
    interests: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, server_default="{}"
    )
    skills: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, server_default="{}"
    )

    # -------------------------------------------------------------------------
    # Preferences — flexible JSONB for notification / recommendation settings
    # Example: {"notify_email": true, "domains": ["ai", "nlp"], "locations": ["remote"]}
    # -------------------------------------------------------------------------
    preferences: Mapped[dict] = mapped_column(
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
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # -------------------------------------------------------------------------
    # Relationships
    # -------------------------------------------------------------------------
    recommendations: Mapped[list["Recommendation"]] = relationship(  # noqa: F821
        "Recommendation",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    notifications: Mapped[list["Notification"]] = relationship(  # noqa: F821
        "Notification",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r} role={self.role}>"