from datetime import UTC, datetime

from sqlalchemy import and_, func, select

from backend.core.enums import NotificationStatus, NotificationType
from backend.models.notification import Notification
from backend.repositories.base_repository import BaseRepository
from backend.schemas.notification import NotificationFilter


class NotificationRepository(BaseRepository[Notification]):
    model = Notification

    # -------------------------------------------------------------------------
    # User feed
    # -------------------------------------------------------------------------

    async def get_for_user(
        self,
        user_id: int,
        filters: NotificationFilter,
    ) -> tuple[list[Notification], int]:
        """Returns (items, total) for a user's notification feed, newest first."""
        conditions = [Notification.user_id == user_id]

        if filters.status:
            conditions.append(Notification.status == filters.status)
        if filters.type:
            conditions.append(Notification.type == filters.type)

        where_clause = and_(*conditions)

        total = (
            await self.db.execute(
                select(func.count())
                .select_from(Notification)
                .where(where_clause)
            )
        ).scalar_one()

        stmt = self._paginate(
            select(Notification)
            .where(where_clause)
            .order_by(Notification.created_at.desc()),
            filters.page,
            filters.page_size,
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total

    async def count_unread(self, user_id: int) -> int:
        return await self.count(
            Notification.user_id == user_id,
            Notification.status == NotificationStatus.UNREAD,
        )

    async def get_recent_unread(
        self, user_id: int, limit: int = 10
    ) -> list[Notification]:
        """Used to populate the notification bell dropdown."""
        result = await self.db.execute(
            select(Notification)
            .where(
                and_(
                    Notification.user_id == user_id,
                    Notification.status == NotificationStatus.UNREAD,
                )
            )
            .order_by(Notification.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    # -------------------------------------------------------------------------
    # Status mutations
    # -------------------------------------------------------------------------

    async def mark_as_read(self, notification: Notification) -> Notification:
        return await self.update_fields(
            notification,
            status=NotificationStatus.READ,
            read_at=datetime.now(UTC),
        )

    async def bulk_mark_as_read(
        self, user_id: int, ids: list[int]
    ) -> int:
        """Bulk-marks the given notification IDs as READ. Returns rows updated."""
        from sqlalchemy import update

        now = datetime.now(UTC)
        result = await self.db.execute(
            update(Notification)
            .where(
                and_(
                    Notification.user_id == user_id,
                    Notification.id.in_(ids),
                    Notification.status == NotificationStatus.UNREAD,
                )
            )
            .values(status=NotificationStatus.READ, read_at=now)
        )
        return result.rowcount  # type: ignore[return-value]

    async def mark_all_read(self, user_id: int) -> int:
        """Marks every unread notification for a user as read. Returns rows updated."""
        from sqlalchemy import update

        now = datetime.now(UTC)
        result = await self.db.execute(
            update(Notification)
            .where(
                and_(
                    Notification.user_id == user_id,
                    Notification.status == NotificationStatus.UNREAD,
                )
            )
            .values(status=NotificationStatus.READ, read_at=now)
        )
        return result.rowcount  # type: ignore[return-value]

    async def archive(self, notification: Notification) -> Notification:
        return await self.update_fields(
            notification, status=NotificationStatus.ARCHIVED
        )

    # -------------------------------------------------------------------------
    # Agent helpers
    # -------------------------------------------------------------------------

    async def get_unsent_email_notifications(self) -> list[Notification]:
        """
        Returns notifications that should have been emailed but haven't yet.
        Polled by AgentNotification's email delivery task.
        """
        result = await self.db.execute(
            select(Notification).where(
                and_(
                    Notification.is_email_sent.is_(False),
                    Notification.type.in_([
                        NotificationType.NEW_OPPORTUNITY,
                        NotificationType.DEADLINE_REMINDER,
                        NotificationType.NEW_RECOMMENDATION,
                    ]),
                )
            )
        )
        return list(result.scalars().all())

    async def mark_email_sent(self, notification: Notification) -> Notification:
        return await self.update_fields(
            notification,
            is_email_sent=True,
            sent_at=datetime.now(UTC),
        )

    async def opportunity_notification_exists(
        self, user_id: int, opportunity_id: int, type: NotificationType
    ) -> bool:
        """
        Prevents duplicate notifications of the same type for the same opportunity.
        AgentNotification checks this before creating a new one.
        """
        return await self.exists(
            Notification.user_id == user_id,
            Notification.opportunity_id == opportunity_id,
            Notification.type == type,
        )

    # -------------------------------------------------------------------------
    # Cleanup
    # -------------------------------------------------------------------------

    async def delete_archived_before(self, cutoff: datetime) -> int:
        """Purges archived notifications older than cutoff. Returns rows deleted."""
        from sqlalchemy import delete

        result = await self.db.execute(
            delete(Notification).where(
                and_(
                    Notification.status == NotificationStatus.ARCHIVED,
                    Notification.created_at < cutoff,
                )
            )
        )
        return result.rowcount  # type: ignore[return-value]