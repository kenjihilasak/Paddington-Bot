"""Message router tests."""

from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.db.models import User
from app.db.repositories import ExchangeOfferRepository
from app.services.conversation_state_service import ConversationStateService
from app.services.event_service import EventService
from app.services.exchange_service import ExchangeService
from app.services.listing_service import ListingService
from app.services.message_router import MessageRouter
from app.services.summary_service import SummaryService


@pytest.mark.asyncio
async def test_router_creates_exchange_offer(session_maker, fake_redis) -> None:
    async with session_maker() as session:
        user = User(wa_id="447700900123", display_name="Kenji")
        session.add(user)
        await session.commit()
        await session.refresh(user)

        settings = get_settings()
        router = MessageRouter(
            settings=settings,
            conversation_state_service=ConversationStateService(fake_redis, session, settings),
            exchange_service=ExchangeService(session, settings),
            listing_service=ListingService(session, settings),
            event_service=EventService(session),
            summary_service=SummaryService(session, settings),
            llm_provider=None,
        )

        result = await router.route_message(
            user=user,
            message_text="I want to exchange 300 soles for pounds in Leeds city centre",
        )

        offers = await ExchangeOfferRepository(session).list(offer_currency="PEN", active_only=True)
        assert "posted your exchange offer" in result.reply_text
        assert len(offers) == 1


@pytest.mark.asyncio
async def test_router_asks_follow_up_for_incomplete_listing(session_maker, fake_redis) -> None:
    async with session_maker() as session:
        user = User(wa_id="447700900124", display_name="Kenji")
        session.add(user)
        await session.commit()
        await session.refresh(user)

        settings = get_settings()
        state_service = ConversationStateService(fake_redis, session, settings)
        router = MessageRouter(
            settings=settings,
            conversation_state_service=state_service,
            exchange_service=ExchangeService(session, settings),
            listing_service=ListingService(session, settings),
            event_service=EventService(session),
            summary_service=SummaryService(session, settings),
            llm_provider=None,
        )

        result = await router.route_message(user=user, message_text="I'm selling a microwave")
        saved_state = await state_service.get_state(user.id)

        assert result.intent.value == "create_listing"
        assert "price" in result.reply_text.lower() or "item" in result.reply_text.lower()
        assert saved_state is not None
        assert saved_state.current_flow.value == "listing_create"

