"""Summary service."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.repositories import CommunityEventRepository, ExchangeOfferRepository, ListingRepository
from app.schemas.summary import SummaryItem, SummaryResponse, SummarySection
from app.services.exchange_service import ExchangeService


class SummaryService:
    """Build API and bot summaries from active records."""

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.exchange_repository = ExchangeOfferRepository(session)
        self.listing_repository = ListingRepository(session)
        self.event_repository = CommunityEventRepository(session)

    async def get_summary(self) -> SummaryResponse:
        """Return the current aggregated summary."""

        limit = self.settings.default_summary_limit
        offers = await self.exchange_repository.list(active_only=True, limit=limit)
        listings = await self.listing_repository.list(active_only=True, limit=limit)
        events = await self.event_repository.list(upcoming_only=True, limit=limit)

        return SummaryResponse(
            generated_at=datetime.now(timezone.utc),
            exchange_offers=SummarySection(
                count=await self.exchange_repository.count_active(),
                items=[
                    SummaryItem(
                        id=item.id,
                        title=f"{item.offer_currency} to {' / '.join(ExchangeService.get_target_currencies(item))}",
                        location=item.location,
                        amount=item.amount,
                        currency=item.offer_currency,
                        secondary_currency=", ".join(ExchangeService.get_target_currencies(item)),
                        description=item.notes,
                    )
                    for item in offers
                ],
            ),
            listings=SummarySection(
                count=await self.listing_repository.count_active(),
                items=[
                    SummaryItem(
                        id=item.id,
                        title=item.title,
                        location=item.location,
                        amount=item.price,
                        currency=item.currency,
                        description=item.description,
                    )
                    for item in listings
                ],
            ),
            events=SummarySection(
                count=await self.event_repository.count_active(),
                items=[
                    SummaryItem(
                        id=item.id,
                        title=item.title,
                        location=item.location,
                        event_date=item.event_date,
                        description=item.description,
                    )
                    for item in events
                ],
            ),
        )

    async def render_compact_text(self, language: str = "en") -> str:
        """Render a compact bot-friendly summary."""

        summary = await self.get_summary()
        if language == "en":
            lines = [
                "Here is the latest community summary:",
                f"Exchange offers: {summary.exchange_offers.count}",
            ]
        else:
            lines = [
                "Aqui tienes el resumen mas reciente de la comunidad:",
                f"Ofertas de cambio: {summary.exchange_offers.count}",
            ]
        for item in summary.exchange_offers.items[:3]:
            if language == "en":
                lines.append(
                    f"- {item.amount} {item.currency} to {item.secondary_currency}"
                    + (f" in {item.location}" if item.location else "")
                )
            else:
                lines.append(
                    f"- {item.amount} {item.currency} por {item.secondary_currency}"
                    + (f" en {item.location}" if item.location else "")
                )

        lines.append(f"Listings: {summary.listings.count}" if language == "en" else f"Anuncios: {summary.listings.count}")
        for item in summary.listings.items[:3]:
            if language == "en":
                lines.append(
                    f"- {item.title} for {item.amount} {item.currency}"
                    + (f" in {item.location}" if item.location else "")
                )
            else:
                lines.append(
                    f"- {item.title} por {item.amount} {item.currency}"
                    + (f" en {item.location}" if item.location else "")
                )

        lines.append(f"Events: {summary.events.count}" if language == "en" else f"Eventos: {summary.events.count}")
        for item in summary.events.items[:3]:
            if language == "en":
                when = item.event_date.strftime("%a %d %b %H:%M") if item.event_date else "date TBD"
                lines.append(f"- {item.title} on {when}" + (f" in {item.location}" if item.location else ""))
            else:
                when = item.event_date.strftime("%d/%m %H:%M") if item.event_date else "fecha pendiente"
                lines.append(f"- {item.title} el {when}" + (f" en {item.location}" if item.location else ""))

        return "\n".join(lines)

