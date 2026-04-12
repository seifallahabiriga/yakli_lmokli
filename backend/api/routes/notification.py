from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import get_current_user, get_db
from backend.core.exceptions import ForbiddenError, NotFoundError
from backend.models.user import User
from backend.repositories.notification_repository import NotificationRepository
from backend.schemas.notification import (
    NotificationBulkStatusUpdate,
    NotificationFilter,
    NotificationListResponse,
    NotificationPublic,
    NotificationStatusUpdate,
    NotificationSummary,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get(
    "/me",
    response_model=NotificationListResponse,
    summary="Get current user's notification feed",
)
async def get_my_notifications(
    filters: NotificationFilter = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = NotificationRepository(db)
    items, total = await repo.get_for_user(current_user.id, filters)
    unread_count = await repo.count_unread(current_user.id)
    pages = max(1, -(-total // filters.page_size))

    return NotificationListResponse(
        items=[NotificationSummary.model_validate(n) for n in items],
        total=total,
        unread_count=unread_count,
        page=filters.page,
        page_size=filters.page_size,
        pages=pages,
    )


@router.get(
    "/me/unread",
    response_model=list[NotificationSummary],
    summary="Get recent unread notifications for the bell dropdown",
)
async def get_unread_notifications(
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = NotificationRepository(db)
    items = await repo.get_recent_unread(current_user.id, limit=limit)
    return [NotificationSummary.model_validate(n) for n in items]


@router.get(
    "/{notification_id}",
    response_model=NotificationPublic,
    summary="Get a single notification with full detail",
)
async def get_notification(
    notification_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = NotificationRepository(db)
    notification = await repo.get_by_id(notification_id)

    if notification is None:
        raise NotFoundError(f"Notification {notification_id} not found.")
    if notification.user_id != current_user.id:
        raise ForbiddenError("You can only view your own notifications.")

    return NotificationPublic.model_validate(notification)


@router.patch(
    "/{notification_id}/status",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Mark a notification as read or archived",
)
async def update_notification_status(
    notification_id: int,
    data: NotificationStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = NotificationRepository(db)
    notification = await repo.get_by_id(notification_id)

    if notification is None:
        raise NotFoundError(f"Notification {notification_id} not found.")
    if notification.user_id != current_user.id:
        raise ForbiddenError("You can only update your own notifications.")

    await repo.update_fields(notification, status=data.status)


@router.post(
    "/me/read-all",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Mark all unread notifications as read",
)
async def mark_all_read(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = NotificationRepository(db)
    await repo.mark_all_read(current_user.id)


@router.post(
    "/me/bulk-status",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Bulk update notification status by IDs",
)
async def bulk_update_status(
    data: NotificationBulkStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = NotificationRepository(db)
    await repo.bulk_mark_as_read(current_user.id, data.ids)