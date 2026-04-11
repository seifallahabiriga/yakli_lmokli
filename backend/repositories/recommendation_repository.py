from sqlalchemy import and_, func, select

from backend.core.enums import RecommendationStatus
from backend.models.recommendation import Recommendation
from backend.repositories.base_repository import BaseRepository
from backend.schemas.recommendation import RecommendationFilter


class RecommendationRepository(BaseRepository[Recommendation]):
    model = Recommendation

    # -------------------------------------------------------------------------
    # Lookups
    # -------------------------------------------------------------------------

    async def get_by_user_and_opportunity(
        self, user_id: int, opportunity_id: int
    ) -> Recommendation | None:
        result = await self.db.execute(
            select(Recommendation).where(
                and_(
                    Recommendation.user_id == user_id,
                    Recommendation.opportunity_id == opportunity_id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def pair_exists(self, user_id: int, opportunity_id: int) -> bool:
        return await self.exists(
            Recommendation.user_id == user_id,
            Recommendation.opportunity_id == opportunity_id,
        )

    # -------------------------------------------------------------------------
    # User feed
    # -------------------------------------------------------------------------

    async def get_for_user(
        self,
        user_id: int,
        filters: RecommendationFilter,
    ) -> tuple[list[Recommendation], int]:
        """
        Returns (items, total) for a user's recommendation feed.
        Ordered by rank ASC (best first), nulls last.
        """
        conditions = [Recommendation.user_id == user_id]

        if filters.status:
            conditions.append(Recommendation.status == filters.status)
        if filters.min_score is not None:
            conditions.append(Recommendation.score >= filters.min_score)

        where_clause = and_(*conditions)

        total = (
            await self.db.execute(
                select(func.count())
                .select_from(Recommendation)
                .where(where_clause)
            )
        ).scalar_one()

        stmt = self._paginate(
            select(Recommendation)
            .where(where_clause)
            .order_by(
                Recommendation.rank.asc().nulls_last(),
                Recommendation.score.desc(),
            ),
            filters.page,
            filters.page_size,
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total

    async def get_top_for_user(
        self,
        user_id: int,
        n: int = 10,
        *,
        status: RecommendationStatus = RecommendationStatus.SCORED,
    ) -> list[Recommendation]:
        """Returns the top-N scored recommendations for a user, for dashboard display."""
        result = await self.db.execute(
            select(Recommendation)
            .where(
                and_(
                    Recommendation.user_id == user_id,
                    Recommendation.status == status,
                )
            )
            .order_by(
                Recommendation.rank.asc().nulls_last(),
                Recommendation.score.desc(),
            )
            .limit(n)
        )
        return list(result.scalars().all())

    # -------------------------------------------------------------------------
    # Bulk agent operations
    # -------------------------------------------------------------------------

    async def get_pending(self) -> list[Recommendation]:
        """Returns all recommendations that haven't been scored yet."""
        result = await self.db.execute(
            select(Recommendation).where(
                Recommendation.status == RecommendationStatus.PENDING
            )
        )
        return list(result.scalars().all())

    async def delete_for_user(self, user_id: int) -> int:
        """
        Wipes all recommendations for a user before a full recompute.
        Returns number of rows deleted.
        """
        from sqlalchemy import delete

        result = await self.db.execute(
            delete(Recommendation).where(Recommendation.user_id == user_id)
        )
        return result.rowcount  # type: ignore[return-value]

    async def bulk_update_ranks(
        self, user_id: int, ranked_ids: list[int]
    ) -> None:
        """
        Assigns ranks to a user's recommendations based on an ordered list of IDs.
        ranked_ids[0] gets rank=1, ranked_ids[1] gets rank=2, etc.
        """
        from sqlalchemy import case, update

        if not ranked_ids:
            return

        rank_map = {rec_id: rank + 1 for rank, rec_id in enumerate(ranked_ids)}
        stmt = (
            update(Recommendation)
            .where(
                and_(
                    Recommendation.user_id == user_id,
                    Recommendation.id.in_(ranked_ids),
                )
            )
            .values(
                rank=case(rank_map, value=Recommendation.id)  # type: ignore[arg-type]
            )
        )
        await self.db.execute(stmt)

    # -------------------------------------------------------------------------
    # Stats
    # -------------------------------------------------------------------------

    async def count_for_user(
        self,
        user_id: int,
        status: RecommendationStatus | None = None,
    ) -> int:
        conditions = [Recommendation.user_id == user_id]
        if status:
            conditions.append(Recommendation.status == status)
        return await self.count(*conditions)

    async def avg_score_for_user(self, user_id: int) -> float | None:
        result = await self.db.execute(
            select(func.avg(Recommendation.score)).where(
                Recommendation.user_id == user_id
            )
        )
        return result.scalar_one_or_none()