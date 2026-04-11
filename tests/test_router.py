"""Message router tests."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.core.config import get_settings
from app.db.models import ExchangeOffer, Listing, ListingCategory, RecordStatus, User
from app.db.repositories import ExchangeOfferRepository
from app.intents.base import IntentClassifier
from app.schemas.bot import IntentResult, IntentType
from app.services.conversation_state_service import ConversationStateService
from app.services.event_service import EventService
from app.services.exchange_service import ExchangeService
from app.services.listing_service import ListingService
from app.services.message_router import MessageRouter
from app.services.summary_service import SummaryService


class FakeIntentClassifier(IntentClassifier):
    """Simple stub intent classifier used by router tests."""

    def __init__(self, intent: IntentType, confidence: float = 0.9) -> None:
        self.intent = intent
        self.confidence = confidence

    async def classify_intent(self, message: str) -> IntentResult:
        return IntentResult(intent=self.intent, confidence=self.confidence, source="embedding")


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
            intent_classifier=None,
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
            intent_classifier=None,
            llm_provider=None,
        )

        result = await router.route_message(user=user, message_text="I'm selling a microwave")
        saved_state = await state_service.get_state(user.id)

        assert result.intent.value == "create_listing"
        assert "price" in result.reply_text.lower() or "item" in result.reply_text.lower()
        assert saved_state is not None
        assert saved_state.current_flow.value == "listing_create"


@pytest.mark.asyncio
async def test_router_handles_simple_sell_command(session_maker, fake_redis) -> None:
    async with session_maker() as session:
        user = User(wa_id="447700900126", display_name="Kenji")
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
            intent_classifier=None,
            llm_provider=None,
        )

        result = await router.route_message(user=user, message_text="sell")
        saved_state = await state_service.get_state(user.id)

        assert result.intent.value == "create_listing"
        assert "what item" in result.reply_text.lower()
        assert saved_state is not None
        assert saved_state.current_flow.value == "listing_create"


@pytest.mark.asyncio
async def test_router_understands_spanish_listing_message(session_maker, fake_redis) -> None:
    async with session_maker() as session:
        user = User(wa_id="447700900127", display_name="Kenji")
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
            intent_classifier=None,
            llm_provider=None,
        )

        result = await router.route_message(
            user=user,
            message_text="Vendo un microondas en Headingley por 25 libras",
        )

        assert result.intent == IntentType.CREATE_LISTING
        assert "he publicado tu anuncio" in result.reply_text.lower()


@pytest.mark.asyncio
async def test_router_replies_in_spanish_for_spanish_help_keyword(session_maker, fake_redis) -> None:
    async with session_maker() as session:
        user = User(wa_id="447700900131", display_name="Kenji")
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
            intent_classifier=None,
            llm_provider=None,
        )

        result = await router.route_message(user=user, message_text="ayuda")

        assert result.intent == IntentType.HELP_MENU
        assert "puedes pedirme" in result.reply_text.lower()
        assert "publicar una oferta de cambio" in result.reply_text.lower()


@pytest.mark.asyncio
async def test_router_defaults_to_spanish_when_language_is_unclear(session_maker, fake_redis) -> None:
    async with session_maker() as session:
        user = User(wa_id="447700900132", display_name="Kenji")
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
            intent_classifier=None,
            llm_provider=None,
        )

        result = await router.route_message(user=user, message_text="???")

        assert result.intent == IntentType.HELP_MENU
        assert "no he entendido" in result.reply_text.lower()
        assert "puedes pedirme" in result.reply_text.lower()


@pytest.mark.asyncio
async def test_router_uses_embedding_classifier_before_llm(session_maker, fake_redis) -> None:
    async with session_maker() as session:
        user = User(wa_id="447700900128", display_name="Kenji")
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
            intent_classifier=FakeIntentClassifier(IntentType.CREATE_LISTING),
            llm_provider=None,
        )

        result = await router.route_message(user=user, message_text="please post this sale for me")
        saved_state = await state_service.get_state(user.id)

        assert result.intent == IntentType.CREATE_LISTING
        assert saved_state is not None
        assert saved_state.current_flow.value == "listing_create"


@pytest.mark.asyncio
async def test_router_keeps_out_of_order_listing_fields_until_title_arrives(session_maker, fake_redis) -> None:
    async with session_maker() as session:
        user = User(wa_id="447700900129", display_name="Kenji")
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
            intent_classifier=None,
            llm_provider=None,
        )

        first_result = await router.route_message(user=user, message_text="vendo")
        second_result = await router.route_message(user=user, message_text="25 pounds")
        state_after_price = await state_service.get_state(user.id)
        third_result = await router.route_message(user=user, message_text="headingley")
        state_after_location = await state_service.get_state(user.id)
        final_result = await router.route_message(user=user, message_text="bicicleta")
        final_state = await state_service.get_state(user.id)

        assert "que articulo" in first_result.reply_text.lower()
        assert "que articulo" in second_result.reply_text.lower()
        assert state_after_price is not None
        assert state_after_price.draft_data["price"] == "25"
        assert state_after_price.draft_data["currency"] == "GBP"
        assert state_after_price.draft_data["_reply_language"] == "es"
        assert "que articulo" in third_result.reply_text.lower()
        assert state_after_location is not None
        assert state_after_location.draft_data["location"] == "Headingley"
        assert final_result.intent == IntentType.CREATE_LISTING
        assert "he publicado tu anuncio" in final_result.reply_text.lower()
        assert final_state is None


@pytest.mark.asyncio
async def test_router_recognizes_spanish_standalone_city_as_location(session_maker, fake_redis) -> None:
    async with session_maker() as session:
        user = User(wa_id="447700900130", display_name="Kenji")
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
            intent_classifier=None,
            llm_provider=None,
        )

        await router.route_message(user=user, message_text="vendo")
        await router.route_message(user=user, message_text="25 libras")
        result = await router.route_message(user=user, message_text="londres")
        saved_state = await state_service.get_state(user.id)

        assert "que articulo" in result.reply_text.lower()
        assert saved_state is not None
        assert saved_state.draft_data["price"] == "25"
        assert saved_state.draft_data["currency"] == "GBP"
        assert saved_state.draft_data["location"] == "London"


@pytest.mark.asyncio
async def test_router_keeps_offer_currency_when_target_currency_arrives_as_fragment(session_maker, fake_redis) -> None:
    async with session_maker() as session:
        user = User(wa_id="447700900133", display_name="Kenji")
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
            intent_classifier=None,
            llm_provider=None,
        )

        await router.route_message(user=user, message_text="cambiar")
        await router.route_message(user=user, message_text="200 soles")
        result = await router.route_message(user=user, message_text="por libras")
        saved_state = await state_service.get_state(user.id)

        assert saved_state is not None
        assert saved_state.draft_data["offer_currency"] == "PEN"
        assert saved_state.draft_data["want_currency"] == "GBP"
        assert "200 pen por gbp" in result.reply_text.lower()
        assert "en que ciudad estas" in result.reply_text.lower()


@pytest.mark.asyncio
async def test_router_reuses_known_city_for_exchange_offer(session_maker, fake_redis) -> None:
    async with session_maker() as session:
        user = User(wa_id="447700900134", display_name="Kenji")
        session.add(user)
        await session.commit()
        await session.refresh(user)

        listing = Listing(
            user_id=user.id,
            category=ListingCategory.ITEM,
            title="Microwave",
            description="Good condition",
            price=Decimal("25"),
            currency="GBP",
            location="Headingley",
            status=RecordStatus.ACTIVE,
        )
        session.add(listing)
        await session.commit()

        settings = get_settings()
        state_service = ConversationStateService(fake_redis, session, settings)
        router = MessageRouter(
            settings=settings,
            conversation_state_service=state_service,
            exchange_service=ExchangeService(session, settings),
            listing_service=ListingService(session, settings),
            event_service=EventService(session),
            summary_service=SummaryService(session, settings),
            intent_classifier=None,
            llm_provider=None,
        )

        result = await router.route_message(
            user=user,
            message_text="Quiero cambiar 200 soles por libras",
        )
        saved_state = await state_service.get_state(user.id)
        offers = await ExchangeOfferRepository(session).list(offer_currency="PEN", active_only=True)

        assert saved_state is None
        assert len(offers) == 1
        assert offers[0].location == "Leeds"
        assert "he publicado tu oferta de cambio" in result.reply_text.lower()
        assert "en leeds" in result.reply_text.lower()


@pytest.mark.asyncio
async def test_router_keeps_multiple_target_currencies_in_exchange_flow(session_maker, fake_redis) -> None:
    async with session_maker() as session:
        user = User(wa_id="447700900135", display_name="Kenji")
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
            intent_classifier=None,
            llm_provider=None,
        )

        first_result = await router.route_message(user=user, message_text="quiero cambiar 200 soles")
        second_result = await router.route_message(user=user, message_text="libras o euros o dolares")
        saved_state = await state_service.get_state(user.id)

        assert "que moneda quieres recibir" in first_result.reply_text.lower()
        assert saved_state is not None
        assert saved_state.current_step == "location"
        assert saved_state.draft_data["offer_currency"] == "PEN"
        assert saved_state.draft_data["want_currency"] == "GBP"
        assert saved_state.draft_data["want_currencies"] == ["GBP", "EUR", "USD"]
        assert "200 pen por gbp, eur o usd" in second_result.reply_text.lower()
        assert "en que ciudad estas" in second_result.reply_text.lower()


@pytest.mark.asyncio
async def test_router_publishes_multi_currency_exchange_offer_with_known_city(session_maker, fake_redis) -> None:
    async with session_maker() as session:
        user = User(wa_id="447700900136", display_name="Kenji")
        session.add(user)
        await session.commit()
        await session.refresh(user)

        listing = Listing(
            user_id=user.id,
            category=ListingCategory.ITEM,
            title="Microwave",
            description="Good condition",
            price=Decimal("25"),
            currency="GBP",
            location="London",
            status=RecordStatus.ACTIVE,
        )
        session.add(listing)
        await session.commit()

        settings = get_settings()
        state_service = ConversationStateService(fake_redis, session, settings)
        router = MessageRouter(
            settings=settings,
            conversation_state_service=state_service,
            exchange_service=ExchangeService(session, settings),
            listing_service=ListingService(session, settings),
            event_service=EventService(session),
            summary_service=SummaryService(session, settings),
            intent_classifier=None,
            llm_provider=None,
        )

        await router.route_message(user=user, message_text="quiero cambiar 200 soles")
        result = await router.route_message(user=user, message_text="libras o euros o dolares")
        saved_state = await state_service.get_state(user.id)
        offers = await ExchangeOfferRepository(session).list(offer_currency="PEN", active_only=True)

        assert saved_state is None
        assert len(offers) == 1
        assert offers[0].want_currency == "GBP"
        assert offers[0].want_currencies == ["GBP", "EUR", "USD"]
        assert offers[0].location == "London"
        assert "gbp, eur o usd" in result.reply_text.lower()
        assert "en london" in result.reply_text.lower()


@pytest.mark.asyncio
async def test_router_allows_currency_direction_correction_after_wrong_exchange_start(
    session_maker,
    fake_redis,
) -> None:
    async with session_maker() as session:
        user = User(wa_id="447700900144", display_name="Kenji")
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
            intent_classifier=None,
            llm_provider=None,
        )

        initial_result = await router.route_message(
            user=user,
            message_text="quiero cambiar 200 soles por libras",
        )
        correction_result_1 = await router.route_message(user=user, message_text="hola quiero soles")
        correction_result_2 = await router.route_message(user=user, message_text="tengo pounds")
        saved_state = await state_service.get_state(user.id)

        assert "200 pen por gbp" in initial_result.reply_text.lower()
        assert "en que ciudad estas" in initial_result.reply_text.lower()
        assert "que moneda quieres ofrecer" in correction_result_1.reply_text.lower()
        assert saved_state is not None
        assert saved_state.current_step == "amount"
        assert saved_state.draft_data["offer_currency"] == "GBP"
        assert saved_state.draft_data["want_currency"] == "PEN"
        assert saved_state.draft_data["want_currencies"] == ["PEN"]
        assert "amount" not in saved_state.draft_data
        assert "gbp por pen" in correction_result_2.reply_text.lower()
        assert "cuanto dinero quieres cambiar" in correction_result_2.reply_text.lower()
        assert "gbp por gbp" not in correction_result_2.reply_text.lower()


@pytest.mark.asyncio
async def test_router_prioritizes_exchange_matches_by_location_scope(session_maker, fake_redis) -> None:
    async with session_maker() as session:
        source_user = User(wa_id="447700900137", display_name="Kenji")
        london_match_user = User(wa_id="447700900138", display_name="Alex")
        manchester_match_user = User(wa_id="447700900139", display_name="Maria")
        edinburgh_match_user = User(wa_id="447700900141", display_name="Sofia")
        session.add_all([source_user, london_match_user, manchester_match_user, edinburgh_match_user])
        await session.commit()
        await session.refresh(source_user)
        await session.refresh(london_match_user)
        await session.refresh(manchester_match_user)
        await session.refresh(edinburgh_match_user)

        session.add(
            Listing(
                user_id=source_user.id,
                category=ListingCategory.ITEM,
                title="Speaker",
                description="Used",
                price=Decimal("40"),
                currency="GBP",
                location="London",
                status=RecordStatus.ACTIVE,
            )
        )
        session.add_all(
            [
                ExchangeOffer(
                    user_id=london_match_user.id,
                    offer_currency="GBP",
                    want_currency="PEN",
                    want_currencies=["PEN"],
                    amount=Decimal("180"),
                    location="London",
                    status=RecordStatus.ACTIVE,
                ),
                ExchangeOffer(
                    user_id=manchester_match_user.id,
                    offer_currency="GBP",
                    want_currency="PEN",
                    want_currencies=["PEN"],
                    amount=Decimal("181"),
                    location="Manchester",
                    status=RecordStatus.ACTIVE,
                ),
                ExchangeOffer(
                    user_id=edinburgh_match_user.id,
                    offer_currency="GBP",
                    want_currency="PEN",
                    want_currencies=["PEN"],
                    amount=Decimal("182"),
                    location="Edinburgh",
                    status=RecordStatus.ACTIVE,
                ),
            ]
        )
        await session.commit()

        settings = get_settings()
        router = MessageRouter(
            settings=settings,
            conversation_state_service=ConversationStateService(fake_redis, session, settings),
            exchange_service=ExchangeService(session, settings),
            listing_service=ListingService(session, settings),
            event_service=EventService(session),
            summary_service=SummaryService(session, settings),
            intent_classifier=None,
            llm_provider=None,
        )

        result = await router.route_message(user=source_user, message_text="Quiero cambiar 200 soles por libras")
        lowered = result.reply_text.lower()

        assert "estos matches activos" in lowered
        assert lowered.index("180.00 gbp") < lowered.index("181.00 gbp")
        assert lowered.index("181.00 gbp") < lowered.index("182.00 gbp")


@pytest.mark.asyncio
async def test_router_marks_latest_exchange_offer_as_resolved(session_maker, fake_redis) -> None:
    async with session_maker() as session:
        user = User(wa_id="447700900142", display_name="Kenji")
        session.add(user)
        await session.commit()
        await session.refresh(user)

        offer = ExchangeOffer(
            user_id=user.id,
            offer_currency="PEN",
            want_currency="GBP",
            want_currencies=["GBP"],
            amount=Decimal("200"),
            location="London",
            status=RecordStatus.ACTIVE,
        )
        session.add(offer)
        await session.commit()

        settings = get_settings()
        router = MessageRouter(
            settings=settings,
            conversation_state_service=ConversationStateService(fake_redis, session, settings),
            exchange_service=ExchangeService(session, settings),
            listing_service=ListingService(session, settings),
            event_service=EventService(session),
            summary_service=SummaryService(session, settings),
            intent_classifier=None,
            llm_provider=None,
        )

        result = await router.route_message(user=user, message_text="ya cambie gracias")
        await session.refresh(offer)

        assert offer.status == RecordStatus.RESOLVED
        assert "resuelta" in result.reply_text.lower()


@pytest.mark.asyncio
async def test_router_marks_latest_listing_as_cancelled(session_maker, fake_redis) -> None:
    async with session_maker() as session:
        user = User(wa_id="447700900143", display_name="Kenji")
        session.add(user)
        await session.commit()
        await session.refresh(user)

        listing = Listing(
            user_id=user.id,
            category=ListingCategory.ITEM,
            title="Microwave",
            description="Good condition",
            price=Decimal("25"),
            currency="GBP",
            location="Headingley",
            status=RecordStatus.ACTIVE,
        )
        session.add(listing)
        await session.commit()

        settings = get_settings()
        router = MessageRouter(
            settings=settings,
            conversation_state_service=ConversationStateService(fake_redis, session, settings),
            exchange_service=ExchangeService(session, settings),
            listing_service=ListingService(session, settings),
            event_service=EventService(session),
            summary_service=SummaryService(session, settings),
            intent_classifier=None,
            llm_provider=None,
        )

        result = await router.route_message(user=user, message_text="ya no quiero recibir mas mensajes")
        await session.refresh(listing)

        assert listing.status == RecordStatus.CANCELLED
        assert "cancelado" in result.reply_text.lower()
