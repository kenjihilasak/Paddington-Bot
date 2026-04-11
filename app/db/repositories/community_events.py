"""Community event repository."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CommunityEvent, RecordStatus


class CommunityEventRepository:
    """Database operations for community events."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, event: CommunityEvent) -> CommunityEvent:
        self.session.add(event)
        await self.session.flush()
        return event

    async def list(
        self,
        *,
        location: str | None = None,
        status: RecordStatus | None = None,
        upcoming_only: bool = True,
        limit: int = 20,
        offset: int = 0,
    ) -> list[CommunityEvent]:
        now = datetime.now(timezone.utc)
        stmt = select(CommunityEvent)
        if location:
            stmt = stmt.where(CommunityEvent.location.ilike(f"%{location}%"))
        if status:
            stmt = stmt.where(CommunityEvent.status == status)
        if upcoming_only:
            stmt = stmt.where(
                CommunityEvent.status == RecordStatus.ACTIVE,
                CommunityEvent.event_date >= now,
            )
        stmt = stmt.order_by(CommunityEvent.event_date.asc()).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_active(self) -> int:
        now = datetime.now(timezone.utc)
        result = await self.session.execute(
            select(func.count(CommunityEvent.id)).where(
                CommunityEvent.status == RecordStatus.ACTIVE,
                CommunityEvent.event_date >= now,
            )
        )
        return int(result.scalar_one())

    async def get_latest_active_for_user(self, user_id: int) -> CommunityEvent | None:
        now = datetime.now(timezone.utc)
        result = await self.session.execute(
            select(CommunityEvent)
            .where(
                CommunityEvent.user_id == user_id,
                CommunityEvent.status == RecordStatus.ACTIVE,
                CommunityEvent.event_date >= now,
            )
            .order_by(CommunityEvent.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
