"""Exchange offer service."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.models import ExchangeOffer, RecordStatus
from app.db.repositories import ExchangeOfferRepository, UserRepository
from app.schemas.exchange_offer import ExchangeOfferCreate


class ExchangeService:
    """Business logic for exchange offers."""

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.repository = ExchangeOfferRepository(session)
        self.user_repository = UserRepository(session)

    async def create_offer(self, payload: ExchangeOfferCreate) -> ExchangeOffer:
        """Create a new exchange offer."""

        user = await self.user_repository.get_by_id(payload.user_id)
        if user is None:
            raise ValueError("User not found.")

        offer = ExchangeOffer(
            user_id=payload.user_id,
            offer_currency=payload.offer_currency.upper(),
            want_currency=payload.want_currency.upper(),
            amount=payload.amount,
            location=payload.location,
            notes=payload.notes,
            status=payload.status,
            expires_at=payload.expires_at
            or datetime.now(timezone.utc) + timedelta(days=self.settings.default_offer_expiry_days),
        )
        await self.repository.create(offer)
        await self.session.commit()
        await self.session.refresh(offer)
        return offer

    async def list_offers(
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
        """List exchange offers using API filter semantics."""

        return await self.repository.list(
            offer_currency=offer_currency,
            want_currency=want_currency,
            location=location,
            status=status,
            active_only=active_only,
            limit=limit,
            offset=offset,
        )

    async def search_offers(
        self,
        *,
        offer_currency: str | None = None,
        want_currency: str | None = None,
        location: str | None = None,
        limit: int | None = None,
    ) -> list[ExchangeOffer]:
        """Search active exchange offers."""

        return await self.repository.list(
            offer_currency=offer_currency,
            want_currency=want_currency,
            location=location,
            active_only=True,
            limit=limit or self.settings.default_summary_limit,
            offset=0,
        )

