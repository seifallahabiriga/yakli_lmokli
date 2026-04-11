from sqlalchemy import select

from backend.core.enums import UserRole
from backend.models.user import User
from backend.repositories.base_repository import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    # -------------------------------------------------------------------------
    # Lookups
    # -------------------------------------------------------------------------

    async def get_by_email(self, email: str) -> User | None:
        result = await self.db.execute(
            select(User).where(User.email == email.lower().strip())
        )
        return result.scalar_one_or_none()

    async def email_exists(self, email: str) -> bool:
        return await self.exists(User.email == email.lower().strip())

    async def get_active_by_email(self, email: str) -> User | None:
        result = await self.db.execute(
            select(User).where(
                User.email == email.lower().strip(),
                User.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()

    # -------------------------------------------------------------------------
    # Filtered lists
    # -------------------------------------------------------------------------

    async def get_by_role(
        self,
        role: UserRole,
        *,
        page: int = 1,
        page_size: int = 50,
    ) -> list[User]:
        stmt = self._paginate(
            select(User).where(User.role == role).order_by(User.created_at.desc()),
            page,
            page_size,
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_active_users(
        self,
        *,
        page: int = 1,
        page_size: int = 50,
    ) -> list[User]:
        stmt = self._paginate(
            select(User)
            .where(User.is_active.is_(True))
            .order_by(User.created_at.desc()),
            page,
            page_size,
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_users_with_skill(self, skill: str) -> list[User]:
        """
        Returns users whose skills array contains the given skill.
        Uses Postgres && (overlap) operator via SQLAlchemy's .any().
        """
        result = await self.db.execute(
            select(User).where(User.skills.any(skill.lower()))  # type: ignore[attr-defined]
        )
        return list(result.scalars().all())

    async def get_users_with_interest(self, interest: str) -> list[User]:
        result = await self.db.execute(
            select(User).where(User.interests.any(interest.lower()))  # type: ignore[attr-defined]
        )
        return list(result.scalars().all())

    # -------------------------------------------------------------------------
    # Counts
    # -------------------------------------------------------------------------

    async def count_by_role(self, role: UserRole) -> int:
        return await self.count(User.role == role)

    async def count_active(self) -> int:
        return await self.count(User.is_active.is_(True))

    # -------------------------------------------------------------------------
    # Auth helpers
    # -------------------------------------------------------------------------

    async def set_last_login(self, user: User) -> User:
        from datetime import UTC, datetime
        return await self.update_fields(user, last_login_at=datetime.now(UTC))

    async def verify_user(self, user: User) -> User:
        return await self.update_fields(user, is_verified=True)

    async def deactivate(self, user: User) -> User:
        return await self.update_fields(user, is_active=False)

    async def set_password(self, user: User, hashed_password: str) -> User:
        return await self.update_fields(user, hashed_password=hashed_password)