"""Listing repository."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Listing, ListingCategory, RecordStatus


class ListingRepository:
    """Database operations for marketplace listings."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, listing: Listing) -> Listing:
        self.session.add(listing)
        await self.session.flush()
        return listing

    async def list(
        self,
        *,
        category: ListingCategory | None = None,
        location: str | None = None,
        search_text: str | None = None,
        status: RecordStatus | None = None,
        active_only: bool = True,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Listing]:
        now = datetime.now(timezone.utc)
        stmt = select(Listing)
        if category:
            stmt = stmt.where(Listing.category == category)
        if location:
            stmt = stmt.where(Listing.location.ilike(f"%{location}%"))
        if search_text:
            stmt = stmt.where(
                Listing.title.ilike(f"%{search_text}%") | Listing.description.ilike(f"%{search_text}%")
            )
        if status:
            stmt = stmt.where(Listing.status == status)
        if active_only:
            stmt = stmt.where(
                Listing.status == RecordStatus.ACTIVE,
                or_(Listing.expires_at.is_(None), Listing.expires_at >= now),
            )
        stmt = stmt.order_by(Listing.created_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_active(self) -> int:
        now = datetime.now(timezone.utc)
        result = await self.session.execute(
            select(func.count(Listing.id)).where(
                Listing.status == RecordStatus.ACTIVE,
                or_(Listing.expires_at.is_(None), Listing.expires_at >= now),
            )
        )
        return int(result.scalar_one())

    async def get_latest_active_for_user(self, user_id: int) -> Listing | None:
        now = datetime.now(timezone.utc)
        result = await self.session.execute(
            select(Listing)
            .where(
                Listing.user_id == user_id,
                Listing.status == RecordStatus.ACTIVE,
                or_(Listing.expires_at.is_(None), Listing.expires_at >= now),
            )
            .order_by(Listing.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

