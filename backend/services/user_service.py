"""
User service — profile management, admin operations, and cache interactions.

Consumed by api/routes/user.py.
Triggers recommendation recompute via the queue when profile changes
would meaningfully affect scoring (skills, interests, preferences).
"""

import json

from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.enums import UserRole
from backend.core.exceptions import ForbiddenError, UserNotFoundError
from backend.models.user import User
from backend.job_queue.producer import enqueue_recommendation_recompute
from backend.job_queue.redis_client import CacheKeys
from backend.repositories.user_repository import UserRepository
from backend.schemas.user import UserUpdate


class UserService:
    def __init__(self, db: AsyncSession, cache) -> None:
        self.db = db
        self.cache = cache
        self.user_repo = UserRepository(db)

    # -------------------------------------------------------------------------
    # Read
    # -------------------------------------------------------------------------

    async def get_by_id(self, user_id: int) -> User:
        """
        Raises:
            UserNotFoundError
        """
        user = await self.user_repo.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError(user_id)
        return user

    async def get_profile(self, user_id: int) -> User:
        """
        Returns cached user profile if available, otherwise loads from DB.
        The profile cache has a short TTL since it's mainly used to avoid
        redundant DB hits within a single request session.
        """
        cache_key = CacheKeys.user_profile(user_id)
        cached = await self.cache.get(cache_key)
        if cached:
            # Return the DB object — cache only used for hot-path reads
            # where we know the profile is fresh. For now, skip deserialization
            # and fall through to DB for correctness.
            pass

        user = await self.user_repo.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError(user_id)
        return user

    async def list_users(
        self,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[User], int]:
        """Admin — paginated user list."""
        users = await self.user_repo.get_active_users(page=page, page_size=page_size)
        total = await self.user_repo.count_active()
        return users, total

    # -------------------------------------------------------------------------
    # Update
    # -------------------------------------------------------------------------

    async def update_profile(
        self,
        user: User,
        data: UserUpdate,
        *,
        requesting_user: User,
    ) -> User:
        """
        Updates a user's profile fields.

        Only the user themselves or an admin can update a profile.
        If skills, interests, or preferences change, triggers a
        recommendation recompute so the feed stays relevant.

        Raises:
            ForbiddenError: requesting user is not the owner or admin.
        """


        if requesting_user.id != user.id and requesting_user.role != UserRole.ADMIN:
            raise ForbiddenError("You can only update your own profile.")

        # Track whether ML-relevant fields changed
        profile_changed = any([
            data.skills is not None and set(data.skills) != set(user.skills or []),
            data.interests is not None and set(data.interests) != set(user.interests or []),
            data.preferences is not None and data.preferences != user.preferences,
            data.academic_level is not None and data.academic_level != user.academic_level,
            data.field_of_study is not None and data.field_of_study != user.field_of_study,
        ])

        update_data = data.model_dump(exclude_unset=True)
        updated_user = await self.user_repo.update(user, update_data)

        # Invalidate profile cache
        await self.cache.delete(CacheKeys.user_profile(user.id))

        # Trigger recommendation recompute for this user only
        if profile_changed:
            enqueue_recommendation_recompute(user_id=user.id)

        return updated_user

    # -------------------------------------------------------------------------
    # Admin operations
    # -------------------------------------------------------------------------

    async def deactivate(self, user_id: int, *, requesting_user: User) -> User:
        """
        Deactivates a user account.

        Raises:
            ForbiddenError: requesting user is not an admin.
            UserNotFoundError: user not found.
        """


        if requesting_user.role != UserRole.ADMIN:
            raise ForbiddenError("Only admins can deactivate accounts.")

        user = await self.user_repo.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError(user_id)

        deactivated = await self.user_repo.deactivate(user)
        await self.cache.delete(CacheKeys.user_profile(user_id))
        return deactivated

    async def verify_user(self, user_id: int) -> User:
        """Marks a user as email-verified."""
        user = await self.user_repo.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError(user_id)
        return await self.user_repo.verify_user(user)

    # -------------------------------------------------------------------------
    # Stats
    # -------------------------------------------------------------------------

    async def get_stats(self) -> dict:
        """Admin dashboard stats."""


        return {
            "total_active": await self.user_repo.count_active(),
            "by_role": {
                role.value: await self.user_repo.count_by_role(role)
                for role in UserRole
            },
        }