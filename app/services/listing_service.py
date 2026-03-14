"""Listing service."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.models import Listing, ListingCategory, RecordStatus
from app.db.repositories import ListingRepository, UserRepository
from app.schemas.listing import ListingCreate


class ListingService:
    """Business logic for marketplace listings."""

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.repository = ListingRepository(session)
        self.user_repository = UserRepository(session)

    async def create_listing(self, payload: ListingCreate) -> Listing:
        """Create a new listing."""

        user = await self.user_repository.get_by_id(payload.user_id)
        if user is None:
            raise ValueError("User not found.")

        listing = Listing(
            user_id=payload.user_id,
            category=payload.category,
            title=payload.title,
            description=payload.description,
            price=payload.price,
            currency=payload.currency.upper(),
            location=payload.location,
            status=payload.status,
            expires_at=payload.expires_at
            or datetime.now(timezone.utc) + timedelta(days=self.settings.default_listing_expiry_days),
        )
        await self.repository.create(listing)
        await self.session.commit()
        await self.session.refresh(listing)
        return listing

    async def list_listings(
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
        """List marketplace listings."""

        return await self.repository.list(
            category=category,
            location=location,
            search_text=search_text,
            status=status,
            active_only=active_only,
            limit=limit,
            offset=offset,
        )

