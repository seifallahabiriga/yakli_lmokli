from typing import Any, Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """
    Generic async repository providing common CRUD operations.

    All domain repositories inherit from this and add query methods
    specific to their model. Direct DB access outside repositories
    is discouraged — keep all SQL in this layer.

    Usage:
        class UserRepository(BaseRepository[User]):
            model = User
    """

    model: type[ModelT]

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # -------------------------------------------------------------------------
    # Create
    # -------------------------------------------------------------------------

    async def create(self, obj: ModelT) -> ModelT:
        """Persists a new model instance and returns it with DB-generated fields."""
        self.db.add(obj)
        await self.db.flush()       # assigns id without committing
        await self.db.refresh(obj)  # loads server defaults (created_at etc.)
        return obj

    async def create_many(self, objs: list[ModelT]) -> list[ModelT]:
        """Bulk-inserts a list of model instances."""
        self.db.add_all(objs)
        await self.db.flush()
        for obj in objs:
            await self.db.refresh(obj)
        return objs

    # -------------------------------------------------------------------------
    # Read
    # -------------------------------------------------------------------------

    async def get_by_id(self, id: int) -> ModelT | None:
        result = await self.db.execute(
            select(self.model).where(self.model.id == id)  # type: ignore[attr-defined]
        )
        return result.scalar_one_or_none()

    async def get_all(
        self,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> list[ModelT]:
        result = await self.db.execute(
            select(self.model).offset(offset).limit(limit)  # type: ignore[arg-type]
        )
        return list(result.scalars().all())

    async def count(self, *filters: Any) -> int:
        stmt = select(func.count()).select_from(self.model)  # type: ignore[arg-type]
        if filters:
            stmt = stmt.where(*filters)
        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def exists(self, *filters: Any) -> bool:
        stmt = select(func.count()).select_from(self.model).where(*filters)  # type: ignore[arg-type]
        result = await self.db.execute(stmt)
        return result.scalar_one() > 0

    # -------------------------------------------------------------------------
    # Update
    # -------------------------------------------------------------------------

    async def update(self, obj: ModelT, data: dict[str, Any]) -> ModelT:
        """
        Applies a dict of field updates to an existing model instance.
        Skips None values so callers can pass partial PATCH payloads directly.
        """
        for field, value in data.items():
            if value is not None and hasattr(obj, field):
                setattr(obj, field, value)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    async def update_fields(self, obj: ModelT, **kwargs: Any) -> ModelT:
        """Convenience wrapper — update(obj, {"field": value}) as keyword args."""
        return await self.update(obj, kwargs)

    # -------------------------------------------------------------------------
    # Delete
    # -------------------------------------------------------------------------

    async def delete(self, obj: ModelT) -> None:
        await self.db.delete(obj)
        await self.db.flush()

    async def delete_by_id(self, id: int) -> bool:
        """Returns True if a row was deleted, False if not found."""
        obj = await self.get_by_id(id)
        if obj is None:
            return False
        await self.delete(obj)
        return True

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _paginate(self, stmt: Any, page: int, page_size: int) -> Any:
        """Applies OFFSET/LIMIT pagination to any SELECT statement."""
        return stmt.offset((page - 1) * page_size).limit(page_size)