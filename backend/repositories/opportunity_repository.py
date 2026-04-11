from datetime import UTC, datetime

from sqlalchemy import and_, func, or_, select, text

from backend.core.enums import OpportunityDomain, OpportunityLevel, OpportunityStatus, OpportunityType
from backend.models.opportunity import Opportunity
from backend.repositories.base_repository import BaseRepository
from backend.schemas.opportunity import OpportunityFilter


class OpportunityRepository(BaseRepository[Opportunity]):
    model = Opportunity

    # -------------------------------------------------------------------------
    # Lookups
    # -------------------------------------------------------------------------

    async def get_by_url(self, url: str) -> Opportunity | None:
        result = await self.db.execute(
            select(Opportunity).where(Opportunity.url == url)
        )
        return result.scalar_one_or_none()

    async def url_exists(self, url: str) -> bool:
        return await self.exists(Opportunity.url == url)

    # -------------------------------------------------------------------------
    # Filtered list + pagination
    # -------------------------------------------------------------------------

    async def get_filtered(
        self,
        filters: OpportunityFilter,
    ) -> tuple[list[Opportunity], int]:
        """
        Returns (items, total_count) applying all active filters.
        Drives GET /opportunities with full filter + pagination support.
        """
        conditions = []

        if filters.type:
            conditions.append(Opportunity.type == filters.type)
        if filters.domain:
            conditions.append(Opportunity.domain == filters.domain)
        if filters.level:
            conditions.append(Opportunity.level == filters.level)
        if filters.status:
            conditions.append(Opportunity.status == filters.status)
        if filters.location_type:
            conditions.append(Opportunity.location_type == filters.location_type)
        if filters.country:
            conditions.append(Opportunity.country.ilike(f"%{filters.country}%"))
        if filters.is_paid is not None:
            conditions.append(Opportunity.is_paid.is_(filters.is_paid))
        if filters.cluster_id is not None:
            conditions.append(Opportunity.cluster_id == filters.cluster_id)
        if filters.deadline_after:
            conditions.append(Opportunity.deadline >= filters.deadline_after)
        if filters.deadline_before:
            conditions.append(Opportunity.deadline <= filters.deadline_before)

        # Full-text search via Postgres tsvector
        if filters.search:
            conditions.append(
                Opportunity.search_vector.op("@@")(  # type: ignore[attr-defined]
                    func.plainto_tsquery("english", filters.search)
                )
            )

        where_clause = and_(*conditions) if conditions else True  # type: ignore[arg-type]

        # Total count (for pagination header)
        count_stmt = (
            select(func.count())
            .select_from(Opportunity)
            .where(where_clause)
        )
        total = (await self.db.execute(count_stmt)).scalar_one()

        # Paginated results
        stmt = self._paginate(
            select(Opportunity)
            .where(where_clause)
            .order_by(Opportunity.created_at.desc()),
            filters.page,
            filters.page_size,
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total

    # -------------------------------------------------------------------------
    # Status management
    # -------------------------------------------------------------------------

    async def get_by_status(self, status: OpportunityStatus) -> list[Opportunity]:
        result = await self.db.execute(
            select(Opportunity)
            .where(Opportunity.status == status)
            .order_by(Opportunity.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_expiring_soon(self, within_days: int = 7) -> list[Opportunity]:
        """Returns active opportunities whose deadline falls within `within_days`."""
        now = datetime.now(UTC)
        cutoff = datetime.fromtimestamp(
            now.timestamp() + within_days * 86400, tz=UTC
        )
        result = await self.db.execute(
            select(Opportunity).where(
                and_(
                    Opportunity.status == OpportunityStatus.ACTIVE,
                    Opportunity.deadline >= now,
                    Opportunity.deadline <= cutoff,
                )
            ).order_by(Opportunity.deadline.asc())
        )
        return list(result.scalars().all())

    async def expire_past_deadline(self) -> int:
        """
        Bulk-marks ACTIVE opportunities past their deadline as EXPIRED.
        Called by a Celery Beat task. Returns number of rows updated.
        """
        from sqlalchemy import update

        now = datetime.now(UTC)
        stmt = (
            update(Opportunity)
            .where(
                and_(
                    Opportunity.status == OpportunityStatus.ACTIVE,
                    Opportunity.deadline < now,
                    Opportunity.deadline.is_not(None),
                )
            )
            .values(status=OpportunityStatus.EXPIRED, updated_at=now)
        )
        result = await self.db.execute(stmt)
        return result.rowcount  # type: ignore[return-value]

    # -------------------------------------------------------------------------
    # ML / agent queries
    # -------------------------------------------------------------------------

    async def get_without_embedding(self) -> list[Opportunity]:
        """Returns opportunities that AgentClassifier hasn't embedded yet."""
        result = await self.db.execute(
            select(Opportunity).where(Opportunity.embedding.is_(None))
        )
        return list(result.scalars().all())

    async def get_needing_cluster_assignment(self) -> list[Opportunity]:
        """
        Returns embedded opportunities flagged for cluster assignment.
        Uses the indexed boolean rather than checking two nullable columns,
        making this query O(flagged_rows) instead of O(all_embedded_rows).
        Called by AgentCluster for both initial assignment and drift detection.
        """
        result = await self.db.execute(
            select(Opportunity).where(
                Opportunity.needs_cluster_assignment.is_(True)
            )
        )
        return list(result.scalars().all())

    async def count_needing_assignment(self) -> int:
        """
        Count of opportunities pending cluster assignment.
        Used by AgentCluster to evaluate drift threshold before deciding
        whether to do a full re-cluster or incremental FAISS assignment.
        """
        return await self.count(Opportunity.needs_cluster_assignment.is_(True))

    async def count_embedded(self) -> int:
        """Total opportunities that have an embedding — denominator for drift %."""
        return await self.count(Opportunity.embedding.is_not(None))

    async def get_all_with_embeddings(self) -> list[Opportunity]:
        """
        Returns all opportunities that have an embedding.
        Used by AgentCluster to rebuild the FAISS index.
        """
        result = await self.db.execute(
            select(Opportunity).where(Opportunity.embedding.is_not(None))
        )
        return list(result.scalars().all())

    async def get_by_domain(
        self,
        domain: OpportunityDomain,
        *,
        status: OpportunityStatus = OpportunityStatus.ACTIVE,
    ) -> list[Opportunity]:
        result = await self.db.execute(
            select(Opportunity).where(
                and_(
                    Opportunity.domain == domain,
                    Opportunity.status == status,
                )
            )
        )
        return list(result.scalars().all())

    async def get_by_cluster(self, cluster_id: int) -> list[Opportunity]:
        result = await self.db.execute(
            select(Opportunity)
            .where(Opportunity.cluster_id == cluster_id)
            .order_by(Opportunity.created_at.desc())
        )
        return list(result.scalars().all())

    # -------------------------------------------------------------------------
    # Stats
    # -------------------------------------------------------------------------

    async def count_by_type(self) -> dict[str, int]:
        result = await self.db.execute(
            select(Opportunity.type, func.count().label("count"))
            .group_by(Opportunity.type)
        )
        return {row.type.value: row.count for row in result.all()}

    async def count_by_domain(self) -> dict[str, int]:
        result = await self.db.execute(
            select(Opportunity.domain, func.count().label("count"))
            .group_by(Opportunity.domain)
        )
        return {row.domain.value: row.count for row in result.all()}

    async def count_by_status(self) -> dict[str, int]:
        result = await self.db.execute(
            select(Opportunity.status, func.count().label("count"))
            .group_by(Opportunity.status)
        )
        return {row.status.value: row.count for row in result.all()}