from sqlalchemy import func, select

from models.cluster import OpportunityCluster
from repositories.base_repository import BaseRepository


class ClusterRepository(BaseRepository[OpportunityCluster]):
    model = OpportunityCluster

    # -------------------------------------------------------------------------
    # Lookups
    # -------------------------------------------------------------------------

    async def get_by_name(self, name: str) -> OpportunityCluster | None:
        result = await self.db.execute(
            select(OpportunityCluster).where(OpportunityCluster.name == name)
        )
        return result.scalar_one_or_none()

    # -------------------------------------------------------------------------
    # Lists
    # -------------------------------------------------------------------------

    async def get_all_ordered(self) -> list[OpportunityCluster]:
        """Returns all clusters sorted by member count descending."""
        result = await self.db.execute(
            select(OpportunityCluster).order_by(
                OpportunityCluster.member_count.desc()
            )
        )
        return list(result.scalars().all())

    async def get_non_empty(self) -> list[OpportunityCluster]:
        result = await self.db.execute(
            select(OpportunityCluster)
            .where(OpportunityCluster.member_count > 0)
            .order_by(OpportunityCluster.member_count.desc())
        )
        return list(result.scalars().all())

    # -------------------------------------------------------------------------
    # Bulk recompute helpers
    # -------------------------------------------------------------------------

    async def delete_all(self) -> int:
        """
        Wipes all clusters before a full recompute.
        Opportunities referencing deleted clusters get cluster_id=NULL
        via the SET NULL foreign key constraint.
        Returns number of rows deleted.
        """
        from sqlalchemy import delete

        result = await self.db.execute(delete(OpportunityCluster))
        return result.rowcount  # type: ignore[return-value]

    async def bulk_create(
        self, clusters: list[OpportunityCluster]
    ) -> list[OpportunityCluster]:
        """Inserts a fresh set of clusters after a recompute cycle."""
        return await self.create_many(clusters)

    async def update_member_count(
        self, cluster_id: int, count: int
    ) -> OpportunityCluster | None:
        cluster = await self.get_by_id(cluster_id)
        if cluster is None:
            return None
        return await self.update_fields(cluster, member_count=count)

    async def update_avg_relevance(
        self, cluster_id: int, avg_score: float
    ) -> OpportunityCluster | None:
        cluster = await self.get_by_id(cluster_id)
        if cluster is None:
            return None
        return await self.update_fields(cluster, avg_relevance_score=avg_score)

    # -------------------------------------------------------------------------
    # Stats
    # -------------------------------------------------------------------------

    async def total_member_count(self) -> int:
        result = await self.db.execute(
            select(func.sum(OpportunityCluster.member_count))
        )
        return result.scalar_one() or 0

    async def get_largest(self, n: int = 5) -> list[OpportunityCluster]:
        result = await self.db.execute(
            select(OpportunityCluster)
            .order_by(OpportunityCluster.member_count.desc())
            .limit(n)
        )
        return list(result.scalars().all())