"""
FastAPI dependencies — injected into route handlers via Depends().

Three categories:
  1. Infrastructure — DB session, Redis cache
  2. Auth — decode JWT, load current user, role guards
  3. Pagination — common query param parsing
"""

from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.enums import UserRole
from backend.core.exceptions import (
    ForbiddenError,
    TokenInvalidError,
    UnauthorizedError,
    UserNotFoundError,
)
from backend.core.security import verify_access_token
from backend.db.session import get_async_db
from backend.models.user import User
from backend.job_queue.redis_client import get_async_redis
from backend.repositories.user_repository import UserRepository

# =============================================================================
# Infrastructure
# =============================================================================

# Re-export so routes import from one place
get_db = get_async_db
get_cache = get_async_redis

# =============================================================================
# Auth
# =============================================================================

_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> User:
    """
    Decodes the Bearer JWT and returns the authenticated User.

    Raises:
        UnauthorizedError: no token provided.
        TokenInvalidError | TokenExpiredError: bad token.
        UserNotFoundError: user deleted after token was issued.
    """
    if credentials is None:
        raise UnauthorizedError("No authentication token provided.")

    payload = verify_access_token(credentials.credentials)

    try:
        user_id = int(payload["sub"])
    except (KeyError, ValueError):
        raise TokenInvalidError()

    user = await UserRepository(db).get_by_id(user_id)
    if user is None or not user.is_active:
        raise UserNotFoundError(user_id)

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Alias — explicit name for routes that want an active-user guard."""
    return current_user


async def get_current_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Raises:
        ForbiddenError: authenticated user is not an admin.
    """
    if current_user.role != UserRole.ADMIN:
        raise ForbiddenError("Admin access required.")
    return current_user


# =============================================================================
# Pagination
# =============================================================================

class PaginationParams:
    """
    Common pagination dependency — inject with Depends(PaginationParams).

    Usage:
        async def list_items(p: PaginationParams = Depends()):
            offset = (p.page - 1) * p.page_size
    """

    def __init__(
        self,
        page: int = 1,
        page_size: int = 20,
    ) -> None:
        self.page = max(1, page)
        self.page_size = min(max(1, page_size), 100)