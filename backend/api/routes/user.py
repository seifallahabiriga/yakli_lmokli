from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import (
    PaginationParams,
    get_cache,
    get_current_admin,
    get_current_user,
    get_db,
)
from backend.models.user import User
from backend.schemas.user import UserAdminView, UserPublic, UserSummary, UserUpdate
from backend.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["users"])


# =============================================================================
# Current user — self-service
# =============================================================================

@router.get(
    "/me",
    response_model=UserPublic,
    summary="Get current user's full profile",
)
async def get_my_profile(
    db: AsyncSession = Depends(get_db),
    cache=Depends(get_cache),
    current_user: User = Depends(get_current_user),
):
    service = UserService(db, cache)
    return await service.get_profile(current_user.id)


@router.patch(
    "/me",
    response_model=UserPublic,
    summary="Update current user's profile",
)
async def update_my_profile(
    data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    cache=Depends(get_cache),
    current_user: User = Depends(get_current_user),
):
    service = UserService(db, cache)
    return await service.update_profile(
        current_user,
        data,
        requesting_user=current_user,
    )


# =============================================================================
# Admin — user management
# =============================================================================

@router.get(
    "/",
    response_model=list[UserSummary],
    summary="List all active users (admin)",
)
async def list_users(
    p: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    cache=Depends(get_cache),
    _: User = Depends(get_current_admin),
):
    service = UserService(db, cache)
    users, _ = await service.list_users(page=p.page, page_size=p.page_size)
    return users


@router.get(
    "/stats",
    summary="User stats for admin dashboard",
)
async def user_stats(
    db: AsyncSession = Depends(get_db),
    cache=Depends(get_cache),
    _: User = Depends(get_current_admin),
):
    service = UserService(db, cache)
    return await service.get_stats()


@router.get(
    "/{user_id}",
    response_model=UserAdminView,
    summary="Get a specific user by ID (admin)",
)
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    cache=Depends(get_cache),
    _: User = Depends(get_current_admin),
):
    service = UserService(db, cache)
    return await service.get_by_id(user_id)


@router.patch(
    "/{user_id}",
    response_model=UserPublic,
    summary="Update any user's profile (admin)",
)
async def admin_update_user(
    user_id: int,
    data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    cache=Depends(get_cache),
    current_user: User = Depends(get_current_admin),
):
    service = UserService(db, cache)
    target = await service.get_by_id(user_id)
    return await service.update_profile(target, data, requesting_user=current_user)


@router.post(
    "/{user_id}/deactivate",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate a user account (admin)",
)
async def deactivate_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    cache=Depends(get_cache),
    current_user: User = Depends(get_current_admin),
):
    service = UserService(db, cache)
    await service.deactivate(user_id, requesting_user=current_user)


@router.post(
    "/{user_id}/verify",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Mark a user as email-verified (admin)",
)
async def verify_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    cache=Depends(get_cache),
    _: User = Depends(get_current_admin),
):
    service = UserService(db, cache)
    await service.verify_user(user_id)