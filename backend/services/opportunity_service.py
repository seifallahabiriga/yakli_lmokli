"""
Opportunity service — the main business logic layer for opportunity management.

Consumed by api/routes/opportunity.py.
Owns:
  - Paginated + filtered opportunity retrieval with Redis caching
  - Manual opportunity creation and status management (admin)
  - Pipeline triggers: embedding, clustering, notifications after status change
  - Dashboard stats aggregation
"""

import hashlib
import json

from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import get_settings
from backend.core.enums import OpportunityStatus, UserRole
from backend.core.exceptions import ConflictError, ForbiddenError, OpportunityNotFoundError
from backend.models.opportunity import Opportunity
from backend.models.user import User
from backend.queue.producer import (
    enqueue_new_opportunity_notifications,
    enqueue_opportunity_embedding,
)
from backend.queue.redis_client import CacheKeys
from backend.repositories.opportunity_repository import OpportunityRepository
from backend.schemas.opportunity import (
    OpportunityCreate,
    OpportunityFilter,
    OpportunityListResponse,
    OpportunitySummary,
    OpportunityUpdate,
)

settings = get_settings()


class OpportunityService:
    def __init__(self, db: AsyncSession, cache) -> None:
        self.db = db
        self.cache = cache
        self.repo = OpportunityRepository(db)

    # -------------------------------------------------------------------------
    # Read — single
    # -------------------------------------------------------------------------

    async def get_by_id(self, opportunity_id: int) -> Opportunity:
        """
        Raises:
            OpportunityNotFoundError
        """
        # Try cache first
        cache_key = CacheKeys.opportunity_detail(opportunity_id)
        cached = await self.cache.get(cache_key)
        if cached:
            # Cached as JSON summary — for full object return from DB
            # (cache is used for summary cards, not full ORM objects)
            pass

        opp = await self.repo.get_by_id(opportunity_id)
        if opp is None:
            raise OpportunityNotFoundError(opportunity_id)
        return opp

    # -------------------------------------------------------------------------
    # Read — list + filter + pagination
    # -------------------------------------------------------------------------

    async def list_opportunities(
        self,
        filters: OpportunityFilter,
    ) -> OpportunityListResponse:
        """
        Returns a paginated, filtered list of opportunities.
        Results are cached in Redis keyed by filter hash.

        Cache strategy:
          - Cache key includes all active filter values + page + page_size.
          - TTL: 30 min (CACHE_TTL_OPPORTUNITIES from config).
          - Cache is invalidated when any opportunity is created or status-changed.
        """
        cache_key = CacheKeys.opportunities_list(
            page=filters.page,
            page_size=filters.page_size,
            filters_hash=self._hash_filters(filters),
        )

        cached = await self.cache.get(cache_key)
        if cached:
            return OpportunityListResponse(**json.loads(cached))

        items, total = await self.repo.get_filtered(filters)
        pages = max(1, -(-total // filters.page_size))   # ceiling division

        summaries = [OpportunitySummary.model_validate(item) for item in items]
        response = OpportunityListResponse(
            items=summaries,
            total=total,
            page=filters.page,
            page_size=filters.page_size,
            pages=pages,
        )

        await self.cache.setex(
            cache_key,
            settings.CACHE_TTL_OPPORTUNITIES,
            response.model_dump_json(),
        )
        return response

    # -------------------------------------------------------------------------
    # Create — admin / scraper API
    # -------------------------------------------------------------------------

    async def create(
        self,
        data: OpportunityCreate,
        *,
        requesting_user: User,
    ) -> Opportunity:
        """
        Manually creates an opportunity (admin endpoint).
        Scrapers write directly via the repository — this is for human entry.

        Raises:
            ForbiddenError: non-admin attempted creation.
            ConflictError: URL already exists.
        """


        if requesting_user.role != UserRole.ADMIN:
            raise ForbiddenError("Only admins can manually create opportunities.")

        if await self.repo.url_exists(data.url):
            raise ConflictError(f"Opportunity with URL '{data.url}' already exists.")

        opp = Opportunity(**data.model_dump())
        created = await self.repo.create(opp)

        # Kick off embedding immediately — don't wait for the 15-min cycle
        enqueue_opportunity_embedding(created.id)

        # Invalidate list cache — new item should appear immediately
        await self._invalidate_list_cache()

        return created

    # -------------------------------------------------------------------------
    # Update — admin
    # -------------------------------------------------------------------------

    async def update(
        self,
        opportunity_id: int,
        data: OpportunityUpdate,
        *,
        requesting_user: User,
    ) -> Opportunity:
        """
        Raises:
            ForbiddenError: non-admin.
            OpportunityNotFoundError.
        """


        if requesting_user.role != UserRole.ADMIN:
            raise ForbiddenError("Only admins can update opportunities.")

        opp = await self.repo.get_by_id(opportunity_id)
        if opp is None:
            raise OpportunityNotFoundError(opportunity_id)

        prev_status = opp.status
        update_data = data.model_dump(exclude_unset=True)
        updated = await self.repo.update(opp, update_data)

        # If status just became ACTIVE, notify matched users
        if (
            prev_status != OpportunityStatus.ACTIVE
            and updated.status == OpportunityStatus.ACTIVE
        ):
            enqueue_new_opportunity_notifications(opportunity_id)

        # Invalidate caches
        await self.cache.delete(CacheKeys.opportunity_detail(opportunity_id))
        await self._invalidate_list_cache()

        return updated

    # -------------------------------------------------------------------------
    # Status transitions
    # -------------------------------------------------------------------------

    async def publish(
        self, opportunity_id: int, *, requesting_user: User
    ) -> Opportunity:
        """Promotes a DRAFT opportunity to ACTIVE."""


        if requesting_user.role != UserRole.ADMIN:
            raise ForbiddenError("Only admins can publish opportunities.")

        opp = await self.repo.get_by_id(opportunity_id)
        if opp is None:
            raise OpportunityNotFoundError(opportunity_id)

        if opp.status == OpportunityStatus.ACTIVE:
            return opp   # idempotent

        updated = await self.repo.update_fields(
            opp, status=OpportunityStatus.ACTIVE
        )
        enqueue_new_opportunity_notifications(opportunity_id)
        await self._invalidate_list_cache()
        return updated

    async def archive(
        self, opportunity_id: int, *, requesting_user: User
    ) -> Opportunity:
        """Manually archives an opportunity."""


        if requesting_user.role != UserRole.ADMIN:
            raise ForbiddenError("Only admins can archive opportunities.")

        opp = await self.repo.get_by_id(opportunity_id)
        if opp is None:
            raise OpportunityNotFoundError(opportunity_id)

        updated = await self.repo.update_fields(
            opp, status=OpportunityStatus.ARCHIVED
        )
        await self.cache.delete(CacheKeys.opportunity_detail(opportunity_id))
        await self._invalidate_list_cache()
        return updated

    # -------------------------------------------------------------------------
    # Stats — dashboard
    # -------------------------------------------------------------------------

    async def get_stats(self) -> dict:
        """
        Aggregated counts for the admin dashboard.
        Not cached — these are fast COUNT(*) GROUP BY queries.
        """
        by_type = await self.repo.count_by_type()
        by_domain = await self.repo.count_by_domain()
        by_status = await self.repo.count_by_status()
        expiring_soon = await self.repo.get_expiring_soon(within_days=7)

        return {
            "by_type": by_type,
            "by_domain": by_domain,
            "by_status": by_status,
            "expiring_within_7_days": len(expiring_soon),
            "total": sum(by_status.values()),
        }

    async def get_expiring_soon(self, within_days: int = 7) -> list[Opportunity]:
        return await self.repo.get_expiring_soon(within_days=within_days)

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def _hash_filters(filters: OpportunityFilter) -> str:
        """
        Produces a short hash of active filter values for use as a cache key suffix.
        Excludes pagination (page/page_size) since those are already in the key.
        """
        filter_dict = filters.model_dump(
            exclude={"page", "page_size"},
            exclude_none=True,
        )
        serialized = json.dumps(filter_dict, sort_keys=True, default=str)
        return hashlib.md5(serialized.encode()).hexdigest()[:12]

    async def _invalidate_list_cache(self) -> None:
        """
        Deletes all opportunity list cache keys.
        Uses Redis SCAN to find keys matching the pattern — avoids KEYS
        which blocks the Redis event loop on large keyspaces.
        """
        cursor = 0
        pattern = "opportunities:list:*"
        while True:
            cursor, keys = await self.cache.scan(cursor, match=pattern, count=100)
            if keys:
                await self.cache.delete(*keys)
            if cursor == 0:
                break