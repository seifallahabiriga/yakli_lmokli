from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import get_cache, get_current_admin, get_current_user, get_db
from backend.core.exceptions import ClusterNotFoundError
from backend.models.user import User
from backend.job_queue.producer import enqueue_cluster_recompute
from backend.repositories.cluster_repository import ClusterRepository
from backend.schemas.cluster import (
    ClusterListResponse,
    ClusterPublic,
    ClusterSummary,
    ClusterWithOpportunities,
)
from backend.schemas.opportunity import OpportunitySummary

router = APIRouter(prefix="/clusters", tags=["clusters"])


@router.get(
    "/",
    response_model=ClusterListResponse,
    summary="List all clusters ordered by member count",
)
async def list_clusters(
    db: AsyncSession = Depends(get_db),
    cache=Depends(get_cache),
    _: User = Depends(get_current_user),
):
    """
    Returns all non-empty clusters sorted by member count.
    Used by the dashboard cluster explorer sidebar.
    """
    import json
    from backend.job_queue.redis_client import CacheKeys

    cache_key = CacheKeys.cluster_list()
    cached = await cache.get(cache_key)
    if cached:
        return ClusterListResponse(**json.loads(cached))

    repo = ClusterRepository(db)
    clusters = await repo.get_non_empty()
    total = len(clusters)

    summaries = [ClusterSummary.model_validate(c) for c in clusters]
    response = ClusterListResponse(items=summaries, total=total)

    from backend.core.config import get_settings
    settings = get_settings()
    await cache.setex(
        cache_key,
        settings.CACHE_TTL_CLUSTERS,
        response.model_dump_json(),
    )
    return response


@router.get(
    "/{cluster_id}",
    response_model=ClusterPublic,
    summary="Get cluster metadata by ID",
)
async def get_cluster(
    cluster_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    repo = ClusterRepository(db)
    cluster = await repo.get_by_id(cluster_id)
    if cluster is None:
        raise ClusterNotFoundError(cluster_id)
    return ClusterPublic.model_validate(cluster)


@router.get(
    "/{cluster_id}/opportunities",
    response_model=ClusterWithOpportunities,
    summary="Get cluster with its member opportunities",
)
async def get_cluster_with_opportunities(
    cluster_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """
    Returns the cluster metadata plus a page of its member opportunities.
    Used by the cluster detail view in the dashboard.
    """
    from backend.repositories.opportunity_repository import OpportunityRepository

    cluster_repo = ClusterRepository(db)
    cluster = await cluster_repo.get_by_id(cluster_id)
    if cluster is None:
        raise ClusterNotFoundError(cluster_id)

    opp_repo = OpportunityRepository(db)
    opportunities = await opp_repo.get_by_cluster(cluster_id)

    result = ClusterWithOpportunities.model_validate(cluster)
    result.opportunities = [
        OpportunitySummary.model_validate(o) for o in opportunities
    ]
    return result


@router.post(
    "/recompute",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger a full cluster recompute (admin)",
)
async def trigger_recompute(
    _: User = Depends(get_current_admin),
):
    """
    Enqueues a full KMeans re-cluster of all embedded opportunities.
    Returns immediately — the task runs asynchronously.
    """
    task = enqueue_cluster_recompute()
    return {"task_id": task.id, "status": "queued"}