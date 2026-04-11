"""Exchange offer repository."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ExchangeOffer, RecordStatus


class ExchangeOfferRepository:
    """Database operations for exchange offers."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, offer: ExchangeOffer) -> ExchangeOffer:
        self.session.add(offer)
        await self.session.flush()
        return offer

    async def list(
        self,
        *,
        offer_currency: str | None = None,
        want_currency: str | None = None,
        location: str | None = None,
        status: RecordStatus | None = None,
        active_only: bool = True,
        limit: int = 20,
        offset: int = 0,
    ) -> list[ExchangeOffer]:
        now = datetime.now(timezone.utc)
        stmt = select(ExchangeOffer)
        if offer_currency:
            stmt = stmt.where(ExchangeOffer.offer_currency == offer_currency.upper())
        if want_currency:
            stmt = stmt.where(ExchangeOffer.want_currency == want_currency.upper())
        if location:
            stmt = stmt.where(ExchangeOffer.location.ilike(f"%{location}%"))
        if status:
            stmt = stmt.where(ExchangeOffer.status == status)
        if active_only:
            stmt = stmt.where(
                ExchangeOffer.status == RecordStatus.ACTIVE,
                or_(ExchangeOffer.expires_at.is_(None), ExchangeOffer.expires_at >= now),
            )
        stmt = stmt.order_by(ExchangeOffer.created_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_active(self) -> int:
        now = datetime.now(timezone.utc)
        result = await self.session.execute(
            select(func.count(ExchangeOffer.id)).where(
                ExchangeOffer.status == RecordStatus.ACTIVE,
                or_(ExchangeOffer.expires_at.is_(None), ExchangeOffer.expires_at >= now),
            )
        )
        return int(result.scalar_one())

    async def get_latest_active_for_user(self, user_id: int) -> ExchangeOffer | None:
        now = datetime.now(timezone.utc)
        result = await self.session.execute(
            select(ExchangeOffer)
            .where(
                ExchangeOffer.user_id == user_id,
                ExchangeOffer.status == RecordStatus.ACTIVE,
                or_(ExchangeOffer.expires_at.is_(None), ExchangeOffer.expires_at >= now),
            )
            .order_by(ExchangeOffer.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_active_candidates_by_offer_currencies(
        self,
        *,
        offer_currencies: list[str],
        exclude_user_id: int,
        limit: int = 50,
    ) -> list[ExchangeOffer]:
        if not offer_currencies:
            return []

        now = datetime.now(timezone.utc)
        result = await self.session.execute(
            select(ExchangeOffer)
            .where(
                ExchangeOffer.user_id != exclude_user_id,
                ExchangeOffer.status == RecordStatus.ACTIVE,
                or_(ExchangeOffer.expires_at.is_(None), ExchangeOffer.expires_at >= now),
                ExchangeOffer.offer_currency.in_(offer_currencies),
            )
            .order_by(ExchangeOffer.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

