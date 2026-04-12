from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import get_cache, get_current_admin, get_current_user, get_db
from backend.models.user import User
from backend.schemas.opportunity import (
    OpportunityCreate,
    OpportunityFilter,
    OpportunityListResponse,
    OpportunityPublic,
    OpportunityUpdate,
)
from backend.services.opportunity_service import OpportunityService

router = APIRouter(prefix="/opportunities", tags=["opportunities"])


@router.get(
    "/",
    response_model=OpportunityListResponse,
    summary="List opportunities with filters and pagination",
)
async def list_opportunities(
    filters: OpportunityFilter = Depends(),
    db: AsyncSession = Depends(get_db),
    cache=Depends(get_cache),
):
    """
    Public endpoint — no auth required.
    Supports filtering by type, domain, level, location, deadline, cluster,
    full-text search, and pagination.
    Results are cached in Redis for 30 minutes per unique filter combination.
    """
    service = OpportunityService(db, cache)
    return await service.list_opportunities(filters)


@router.get(
    "/stats",
    summary="Opportunity stats by type, domain, and status (admin)",
)
async def opportunity_stats(
    db: AsyncSession = Depends(get_db),
    cache=Depends(get_cache),
    _: User = Depends(get_current_admin),
):
    service = OpportunityService(db, cache)
    return await service.get_stats()


@router.get(
    "/expiring-soon",
    response_model=list[OpportunityPublic],
    summary="Opportunities expiring within N days",
)
async def expiring_soon(
    within_days: int = Query(7, ge=1, le=30),
    db: AsyncSession = Depends(get_db),
    cache=Depends(get_cache),
    _: User = Depends(get_current_user),
):
    service = OpportunityService(db, cache)
    return await service.get_expiring_soon(within_days=within_days)


@router.get(
    "/{opportunity_id}",
    response_model=OpportunityPublic,
    summary="Get a single opportunity by ID",
)
async def get_opportunity(
    opportunity_id: int,
    db: AsyncSession = Depends(get_db),
    cache=Depends(get_cache),
):
    service = OpportunityService(db, cache)
    return await service.get_by_id(opportunity_id)


@router.post(
    "/",
    response_model=OpportunityPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Manually create an opportunity (admin)",
)
async def create_opportunity(
    data: OpportunityCreate,
    db: AsyncSession = Depends(get_db),
    cache=Depends(get_cache),
    current_user: User = Depends(get_current_admin),
):
    service = OpportunityService(db, cache)
    return await service.create(data, requesting_user=current_user)


@router.patch(
    "/{opportunity_id}",
    response_model=OpportunityPublic,
    summary="Update an opportunity (admin)",
)
async def update_opportunity(
    opportunity_id: int,
    data: OpportunityUpdate,
    db: AsyncSession = Depends(get_db),
    cache=Depends(get_cache),
    current_user: User = Depends(get_current_admin),
):
    service = OpportunityService(db, cache)
    return await service.update(opportunity_id, data, requesting_user=current_user)


@router.post(
    "/{opportunity_id}/publish",
    response_model=OpportunityPublic,
    summary="Promote a DRAFT opportunity to ACTIVE (admin)",
)
async def publish_opportunity(
    opportunity_id: int,
    db: AsyncSession = Depends(get_db),
    cache=Depends(get_cache),
    current_user: User = Depends(get_current_admin),
):
    service = OpportunityService(db, cache)
    return await service.publish(opportunity_id, requesting_user=current_user)


@router.post(
    "/{opportunity_id}/archive",
    response_model=OpportunityPublic,
    summary="Archive an opportunity (admin)",
)
async def archive_opportunity(
    opportunity_id: int,
    db: AsyncSession = Depends(get_db),
    cache=Depends(get_cache),
    current_user: User = Depends(get_current_admin),
):
    service = OpportunityService(db, cache)
    return await service.archive(opportunity_id, requesting_user=current_user)