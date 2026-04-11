"""Exchange offer service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.models import ExchangeOffer, RecordStatus
from app.db.repositories import ExchangeOfferRepository, UserRepository
from app.schemas.exchange_offer import ExchangeOfferCreate
from app.services.exceptions import ResourceNotFoundError


LOCATION_SCOPE_BY_NAME = {
    "Leeds": ("Leeds", "England", "United Kingdom", "Europe"),
    "Leeds City Centre": ("Leeds", "England", "United Kingdom", "Europe"),
    "Headingley": ("Leeds", "England", "United Kingdom", "Europe"),
    "Hyde Park": ("Leeds", "England", "United Kingdom", "Europe"),
    "Roundhay": ("Leeds", "England", "United Kingdom", "Europe"),
    "Bradford": ("Bradford", "England", "United Kingdom", "Europe"),
    "York": ("York", "England", "United Kingdom", "Europe"),
    "Sheffield": ("Sheffield", "England", "United Kingdom", "Europe"),
    "Manchester": ("Manchester", "England", "United Kingdom", "Europe"),
    "Manchester City Centre": ("Manchester", "England", "United Kingdom", "Europe"),
    "London": ("London", "England", "United Kingdom", "Europe"),
    "Birmingham": ("Birmingham", "England", "United Kingdom", "Europe"),
    "Liverpool": ("Liverpool", "England", "United Kingdom", "Europe"),
    "Bristol": ("Bristol", "England", "United Kingdom", "Europe"),
    "Oxford": ("Oxford", "England", "United Kingdom", "Europe"),
    "Cambridge": ("Cambridge", "England", "United Kingdom", "Europe"),
    "Southampton": ("Southampton", "England", "United Kingdom", "Europe"),
    "Portsmouth": ("Portsmouth", "England", "United Kingdom", "Europe"),
    "Brighton": ("Brighton", "England", "United Kingdom", "Europe"),
    "Nottingham": ("Nottingham", "England", "United Kingdom", "Europe"),
    "Leicester": ("Leicester", "England", "United Kingdom", "Europe"),
    "Coventry": ("Coventry", "England", "United Kingdom", "Europe"),
    "Newcastle": ("Newcastle", "England", "United Kingdom", "Europe"),
    "Edinburgh": ("Edinburgh", "Scotland", "United Kingdom", "Europe"),
    "Glasgow": ("Glasgow", "Scotland", "United Kingdom", "Europe"),
    "Cardiff": ("Cardiff", "Wales", "United Kingdom", "Europe"),
    "Belfast": ("Belfast", "Northern Ireland", "United Kingdom", "Europe"),
}


@dataclass(slots=True)
class ExchangeMatchCandidate:
    """Potential reciprocal exchange match."""

    offer: ExchangeOffer
    score: int
    rank_reason: str


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
            raise ResourceNotFoundError("User not found.")

        offer = ExchangeOffer(
            user_id=payload.user_id,
            offer_currency=payload.offer_currency.upper(),
            want_currency=payload.want_currency.upper(),
            want_currencies=[currency.upper() for currency in payload.want_currencies],
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

        fetch_limit = max(limit + offset, 100) if want_currency else limit
        offers = await self.repository.list(
            offer_currency=offer_currency,
            want_currency=None if want_currency else want_currency,
            location=location,
            status=status,
            active_only=active_only,
            limit=fetch_limit,
            offset=0 if want_currency else offset,
        )
        if want_currency:
            normalized_want = want_currency.upper()
            offers = [
                offer for offer in offers if normalized_want in self.get_target_currencies(offer)
            ]
            offers = offers[offset : offset + limit]
        return offers

    async def search_offers(
        self,
        *,
        offer_currency: str | None = None,
        want_currency: str | None = None,
        location: str | None = None,
        limit: int | None = None,
    ) -> list[ExchangeOffer]:
        """Search active exchange offers."""

        return await self.list_offers(
            offer_currency=offer_currency,
            want_currency=want_currency,
            location=location,
            active_only=True,
            limit=limit or self.settings.default_summary_limit,
            offset=0,
        )

    async def get_latest_user_location(self, user_id: int) -> tuple[datetime, str] | None:
        """Return the user's most recent exchange-offer location, if any."""

        result = await self.session.execute(
            select(ExchangeOffer.created_at, ExchangeOffer.location)
            .where(
                ExchangeOffer.user_id == user_id,
                ExchangeOffer.location.is_not(None),
            )
            .order_by(ExchangeOffer.created_at.desc())
            .limit(1)
        )
        row = result.first()
        if row is None:
            return None

        created_at, location = row
        if location is None:
            return None
        return created_at, location

    async def get_latest_active_offer_for_user(self, user_id: int) -> ExchangeOffer | None:
        """Return the user's most recent active exchange offer."""

        return await self.repository.get_latest_active_for_user(user_id)

    async def update_offer_status(self, offer: ExchangeOffer, status: RecordStatus) -> ExchangeOffer:
        """Persist a new lifecycle status for an exchange offer."""

        offer.status = status
        await self.session.commit()
        await self.session.refresh(offer)
        return offer

    async def find_ranked_matches(
        self,
        offer: ExchangeOffer,
        *,
        limit: int | None = None,
    ) -> list[ExchangeMatchCandidate]:
        """Return reciprocal active offers ranked by closeness and preference."""

        target_currencies = self.get_target_currencies(offer)
        candidates = await self.repository.list_active_candidates_by_offer_currencies(
            offer_currencies=target_currencies,
            exclude_user_id=offer.user_id,
            limit=max((limit or self.settings.default_summary_limit) * 5, 20),
        )

        ranked: list[ExchangeMatchCandidate] = []
        for candidate in candidates:
            if not self._offer_accepts_currency(candidate, offer.offer_currency):
                continue
            score, reason = self._score_match(source_offer=offer, candidate_offer=candidate)
            ranked.append(
                ExchangeMatchCandidate(
                    offer=candidate,
                    score=score,
                    rank_reason=reason,
                )
            )

        ranked.sort(key=lambda item: (item.score, item.offer.created_at), reverse=True)
        return ranked[: limit or self.settings.default_summary_limit]

    @staticmethod
    def get_target_currencies(offer: ExchangeOffer) -> list[str]:
        """Return every acceptable target currency for the offer."""

        currencies: list[str] = []
        for currency in list(offer.want_currencies or []) + [offer.want_currency]:
            normalized = (currency or "").strip().upper()
            if normalized and normalized not in currencies:
                currencies.append(normalized)
        return currencies

    @staticmethod
    def _offer_accepts_currency(offer: ExchangeOffer, currency: str) -> bool:
        normalized = currency.upper()
        return normalized in ExchangeService.get_target_currencies(offer)

    def _score_match(self, *, source_offer: ExchangeOffer, candidate_offer: ExchangeOffer) -> tuple[int, str]:
        score = 100
        score += self._currency_preference_bonus(
            accepted_currencies=self.get_target_currencies(source_offer),
            matched_currency=candidate_offer.offer_currency,
            base_bonus=15,
        )
        score += self._currency_preference_bonus(
            accepted_currencies=self.get_target_currencies(candidate_offer),
            matched_currency=source_offer.offer_currency,
            base_bonus=10,
        )

        proximity_score, reason = self._score_location_proximity(
            source_offer.location,
            candidate_offer.location,
        )
        score += proximity_score
        return score, reason

    @staticmethod
    def _currency_preference_bonus(
        *,
        accepted_currencies: list[str],
        matched_currency: str,
        base_bonus: int,
    ) -> int:
        normalized_currency = matched_currency.upper()
        for index, currency in enumerate(accepted_currencies):
            if currency != normalized_currency:
                continue
            return max(base_bonus - (index * 3), 3)
        return 0

    def _score_location_proximity(
        self,
        source_location: str | None,
        candidate_location: str | None,
    ) -> tuple[int, str]:
        if not source_location or not candidate_location:
            return 0, "sin ubicacion comparable"

        source_scope = LOCATION_SCOPE_BY_NAME.get(source_location)
        candidate_scope = LOCATION_SCOPE_BY_NAME.get(candidate_location)
        if source_scope is None or candidate_scope is None:
            if source_location == candidate_location:
                return 40, "misma ciudad"
            return 0, "ubicacion distinta"

        if source_scope[0] == candidate_scope[0]:
            return 40, "misma ciudad"
        if source_scope[1] == candidate_scope[1]:
            return 30, "misma region"
        if source_scope[2] == candidate_scope[2]:
            return 20, "mismo pais"
        if source_scope[3] == candidate_scope[3]:
            return 10, "mismo continente"
        return 0, "otro continente"
