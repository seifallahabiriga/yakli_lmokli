from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import get_cache, get_current_user, get_db
from backend.models.user import User
from backend.repositories.recommendation_repository import RecommendationRepository
from backend.schemas.recommendation import (
    RecommendationFilter,
    RecommendationListResponse,
    RecommendationPublic,
    RecommendationStatusUpdate,
    RecommendationSummary,
)
from backend.core.exceptions import ForbiddenError, RecommendationNotFoundError
from backend.job_queue.producer import enqueue_recommendation_recompute

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.get(
    "/me",
    response_model=RecommendationListResponse,
    summary="Get current user's personalised recommendation feed",
)
async def get_my_recommendations(
    filters: RecommendationFilter = Depends(),
    db: AsyncSession = Depends(get_db),
    cache=Depends(get_cache),
    current_user: User = Depends(get_current_user),
):
    repo = RecommendationRepository(db)
    items, total = await repo.get_for_user(current_user.id, filters)
    pages = max(1, -(-total // filters.page_size))
    summaries = [RecommendationSummary.model_validate(r) for r in items]
    return RecommendationListResponse(
        items=summaries,
        total=total,
        page=filters.page,
        page_size=filters.page_size,
        pages=pages,
    )


@router.get(
    "/me/top",
    response_model=list[RecommendationSummary],
    summary="Get current user's top-N recommendations for dashboard display",
)
async def get_my_top_recommendations(
    n: int = 10,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = RecommendationRepository(db)
    items = await repo.get_top_for_user(current_user.id, n=n)
    return [RecommendationSummary.model_validate(r) for r in items]


@router.get(
    "/{recommendation_id}",
    response_model=RecommendationPublic,
    summary="Get a single recommendation with full opportunity detail",
)
async def get_recommendation(
    recommendation_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = RecommendationRepository(db)
    rec = await repo.get_by_id(recommendation_id)

    if rec is None:
        raise RecommendationNotFoundError(recommendation_id)
    if rec.user_id != current_user.id:
        raise ForbiddenError("You can only view your own recommendations.")

    # Mark as viewed if first time
    if rec.viewed_at is None:
        from datetime import UTC, datetime
        await repo.update_fields(rec, viewed_at=datetime.now(UTC))

    return RecommendationPublic.model_validate(rec)


@router.patch(
    "/{recommendation_id}/status",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Update recommendation status (dismiss or mark as applied)",
)
async def update_recommendation_status(
    recommendation_id: int,
    data: RecommendationStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = RecommendationRepository(db)
    rec = await repo.get_by_id(recommendation_id)

    if rec is None:
        raise RecommendationNotFoundError(recommendation_id)
    if rec.user_id != current_user.id:
        raise ForbiddenError("You can only update your own recommendations.")

    await repo.update_fields(rec, status=data.status)


@router.post(
    "/me/recompute",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger a recommendation recompute for the current user",
)
async def trigger_recompute(
    current_user: User = Depends(get_current_user),
):
    """
    Enqueues a recommendation recompute task for the current user.
    Returns immediately — the task runs asynchronously.
    Use after a significant profile update to refresh the feed without waiting
    for the next scheduled cycle.
    """
    task = enqueue_recommendation_recompute(user_id=current_user.id)
    return {"task_id": task.id, "status": "queued"}