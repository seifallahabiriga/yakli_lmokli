from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from backend.core.enums import AcademicLevel, UserRole


# =============================================================================
# Shared base
# =============================================================================

class UserBase(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=255)
    academic_level: AcademicLevel | None = None
    institution: str | None = Field(None, max_length=255)
    field_of_study: str | None = Field(None, max_length=255)
    bio: str | None = None
    interests: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    preferences: dict = Field(default_factory=dict)

    @field_validator("interests", "skills", mode="before")
    @classmethod
    def lowercase_list(cls, v: list[str]) -> list[str]:
        return [item.lower().strip() for item in v if item.strip()]


# =============================================================================
# Request schemas
# =============================================================================

class UserCreate(UserBase):
    """Used at POST /auth/register."""
    password: str = Field(..., min_length=8, max_length=128)


class UserUpdate(BaseModel):
    """All fields optional — PATCH semantics."""
    full_name: str | None = Field(None, min_length=2, max_length=255)
    academic_level: AcademicLevel | None = None
    institution: str | None = Field(None, max_length=255)
    field_of_study: str | None = Field(None, max_length=255)
    bio: str | None = None
    interests: list[str] | None = None
    skills: list[str] | None = None
    preferences: dict | None = None

    @field_validator("interests", "skills", mode="before")
    @classmethod
    def lowercase_list(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        return [item.lower().strip() for item in v if item.strip()]


class UserUpdatePassword(BaseModel):
    current_password: str = Field(..., min_length=8)
    new_password: str = Field(..., min_length=8, max_length=128)


# =============================================================================
# Response schemas
# =============================================================================

class UserPublic(BaseModel):
    """Returned to the authenticated user — includes all profile fields."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
    role: UserRole
    is_active: bool
    is_verified: bool
    academic_level: AcademicLevel | None
    institution: str | None
    field_of_study: str | None
    bio: str | None
    interests: list[str]
    skills: list[str]
    preferences: dict
    created_at: datetime
    updated_at: datetime
    last_login_at: datetime | None


class UserSummary(BaseModel):
    """Lightweight — embedded inside recommendations, notifications, etc."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: EmailStr
    role: UserRole
    academic_level: AcademicLevel | None


class UserAdminView(UserPublic):
    """Extended view for admin routes — same fields as UserPublic for now,
    extendable with internal flags without touching the public schema."""
    pass


# =============================================================================
# Auth schemas
# =============================================================================

class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPayload(BaseModel):
    """Decoded JWT payload — used internally in auth dependencies."""
    sub: str
    type: str
    role: str | None = None
    exp: int | None = None
    iat: int | None = None