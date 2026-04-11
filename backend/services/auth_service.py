"""
Auth service — all authentication business logic.

Consumed by api/routes/auth.py.
Never touches HTTP directly — returns domain objects and raises
domain exceptions that the route layer maps to HTTP responses.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.exceptions import (
    InvalidCredentialsError,
    TokenInvalidError,
    UserAlreadyExistsError,
    UserNotFoundError,
)
from backend.core.security import (
    create_token_pair,
    hash_password,
    verify_password,
    verify_refresh_token,
)
from backend.models.user import User
from backend.repositories.user_repository import UserRepository
from backend.schemas.user import TokenResponse, UserCreate


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.user_repo = UserRepository(db)

    # -------------------------------------------------------------------------
    # Register
    # -------------------------------------------------------------------------

    async def register(self, data: UserCreate) -> User:
        """
        Creates a new user account.

        Raises:
            UserAlreadyExistsError: email already registered.
        """
        if await self.user_repo.email_exists(data.email):
            raise UserAlreadyExistsError(data.email)

        user = User(
            email=data.email.lower().strip(),
            full_name=data.full_name,
            hashed_password=hash_password(data.password),
            academic_level=data.academic_level,
            institution=data.institution,
            field_of_study=data.field_of_study,
            bio=data.bio,
            interests=data.interests,
            skills=data.skills,
            preferences=data.preferences,
        )
        return await self.user_repo.create(user)

    # -------------------------------------------------------------------------
    # Login
    # -------------------------------------------------------------------------

    async def login(self, email: str, password: str) -> TokenResponse:
        """
        Authenticates a user and returns a token pair.

        Raises:
            InvalidCredentialsError: email not found or wrong password.
        """
        user = await self.user_repo.get_active_by_email(email)
        if user is None:
            raise InvalidCredentialsError()

        if not verify_password(password, user.hashed_password):
            raise InvalidCredentialsError()

        await self.user_repo.set_last_login(user)

        tokens = create_token_pair(user_id=user.id, role=user.role.value)
        return TokenResponse(**tokens)

    # -------------------------------------------------------------------------
    # Refresh
    # -------------------------------------------------------------------------

    async def refresh(self, refresh_token: str) -> TokenResponse:
        """
        Issues a new access + refresh token pair given a valid refresh token.

        Raises:
            TokenInvalidError | TokenExpiredError: invalid or expired token.
            UserNotFoundError: user deleted between token issue and refresh.
        """
        payload = verify_refresh_token(refresh_token)
        user_id = int(payload["sub"])

        user = await self.user_repo.get_by_id(user_id)
        if user is None or not user.is_active:
            raise UserNotFoundError(user_id)

        tokens = create_token_pair(user_id=user.id, role=user.role.value)
        return TokenResponse(**tokens)

    # -------------------------------------------------------------------------
    # Password change
    # -------------------------------------------------------------------------

    async def change_password(
        self,
        user: User,
        current_password: str,
        new_password: str,
    ) -> None:
        """
        Changes a user's password after verifying the current one.

        Raises:
            InvalidCredentialsError: current password is wrong.
        """
        if not verify_password(current_password, user.hashed_password):
            raise InvalidCredentialsError()

        await self.user_repo.set_password(user, hash_password(new_password))