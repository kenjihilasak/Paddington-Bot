"""Inbound message routing and bot flow orchestration."""

from __future__ import annotations

import logging
import re
import unicodedata
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from zoneinfo import ZoneInfo

import dateparser

from app.core.config import Settings
from app.db.models import ConversationFlow, ListingCategory, RecordStatus, User
from app.intents.base import IntentClassifier
from app.llm.base import LLMProvider
from app.schemas.bot import BotRouteResult, IntentResult, IntentType
from app.schemas.event import CommunityEventCreate
from app.schemas.exchange_offer import ExchangeOfferCreate
from app.schemas.listing import ListingCreate
from app.services.conversation_state_service import ConversationStateService
from app.services.event_service import EventService
from app.services.exchange_service import ExchangeService
from app.services.listing_service import ListingService
from app.services.summary_service import SummaryService


logger = logging.getLogger(__name__)


def _normalize_lookup_text(message_text: str) -> str:
    normalized = unicodedata.normalize("NFKD", message_text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return " ".join(ascii_text.lower().strip().split())

CURRENCY_ALIASES = {
    "pound": "GBP",
    "pounds": "GBP",
    "libra": "GBP",
    "libras": "GBP",
    "gbp": "GBP",
    "sterling": "GBP",
    "euro": "EUR",
    "euros": "EUR",
    "eur": "EUR",
    "sol": "PEN",
    "soles": "PEN",
    "pen": "PEN",
    "dolar": "USD",
    "dolares": "USD",
    "dollar": "USD",
    "dollars": "USD",
    "usd": "USD",
}
CURRENCY_WORD_PATTERN = re.compile(
    r"\b(pounds?|libras?|gbp|sterling|euros?|eur|soles?|pen|d[oó]lares?|dollars?|usd)\b",
    re.IGNORECASE,
)
AMOUNT_WITH_CURRENCY_PATTERN = re.compile(
    r"(?P<amount>\d+(?:\.\d+)?)\s*(?P<currency>pounds?|libras?|gbp|sterling|euros?|eur|soles?|pen|d[oó]lares?|dollars?|usd)",
    re.IGNORECASE,
)
PRICE_PATTERN = re.compile(
    r"\b(?:for|por|price(?:d)? at|precio(?: de)?|a)\s*(?P<amount>\d+(?:\.\d+)?)\s*(?P<currency>pounds?|libras?|gbp|sterling|euros?|eur|soles?|pen|d[oó]lares?|dollars?|usd)?",
    re.IGNORECASE,
)
HELP_KEYWORDS = ("help", "menu", "options", "ayuda", "opciones")
SUMMARY_KEYWORDS = ("summary", "recap", "overview", "resumen")
SEARCH_MARKERS = (
    "show me",
    "find",
    "search",
    "do you have",
    "anyone",
    "looking for",
    "muestrame",
    "muestame",
    "buscar",
    "busca",
    "tienes",
    "alguien",
    "quiero ver",
)
LISTING_CREATE_MARKERS = (
    "i'm selling",
    "i am selling",
    "selling",
    "for sale",
    "vendo",
    "estoy vendiendo",
    "quiero vender",
    "en venta",
)
LISTING_SEARCH_MARKERS = (
    "show me listings",
    "find listings",
    "search listings",
    "browse listings",
    "muestrame anuncios",
    "buscar anuncios",
    "ver anuncios",
    "buscar publicaciones",
    "ver publicaciones",
)
EVENT_KEYWORDS = (
    "event",
    "match",
    "meetup",
    "meeting",
    "workshop",
    "football",
    "evento",
    "partido",
    "reunion",
    "taller",
)
DAY_KEYWORDS = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
    "lunes",
    "martes",
    "miercoles",
    "jueves",
    "viernes",
    "sabado",
    "domingo",
)
SELL_COMMANDS = ("sell", "selling", "vendo", "vender")
DEFAULT_REPLY_LANGUAGE = "es"
ENGLISH_LANGUAGE_PHRASES = (
    "i want",
    "i'm selling",
    "i am selling",
    "for sale",
    "show me",
    "find",
    "search",
    "browse",
    "there is",
    "there's",
    "there will be",
)
SPANISH_LANGUAGE_PHRASES = (
    "quiero",
    "estoy vendiendo",
    "en venta",
    "muestrame",
    "muestame",
    "buscar",
    "busca",
    "quiero ver",
    "hay",
    "habra",
    "habrÃ¡",
    "unete a",
)
ENGLISH_LANGUAGE_WORDS = {
    "help",
    "summary",
    "sell",
    "selling",
    "exchange",
    "listing",
    "listings",
    "event",
    "events",
    "please",
    "sale",
    "post",
    "show",
}
SPANISH_LANGUAGE_WORDS = {
    "ayuda",
    "resumen",
    "vendo",
    "vender",
    "cambio",
    "anuncio",
    "anuncios",
    "evento",
    "eventos",
    "publicar",
    "publica",
}
SPANISH_LANGUAGE_HINTS = ("\u00e1", "\u00e9", "\u00ed", "\u00f3", "\u00fa", "\u00f1", "\u00bf", "\u00a1")
EXCHANGE_KEYWORDS = ("exchange", "changing", "cambio", "cambiar", "cambiaria", "cambiaría")
EXCHANGE_RESOLVED_MARKERS = (
    "ya cambie",
    "ya cambie gracias",
    "ya cambie, gracias",
    "ya cambie muchas gracias",
    "ya cambié",
    "ya cambié gracias",
    "already exchanged",
    "exchange done",
)
LISTING_RESOLVED_MARKERS = (
    "ya vendi",
    "ya vendi gracias",
    "ya vendí",
    "ya vendí gracias",
    "sold already",
    "already sold",
)
GENERIC_RESOLVED_MARKERS = ("resolved", "resuelto", "done", "hecho")
CANCELLED_MARKERS = (
    "ya no quiero recibir mas ofertas",
    "ya no quiero recibir más ofertas",
    "ya no quiero recibir mas mensajes",
    "ya no quiero recibir más mensajes",
    "no more offers",
    "no more messages",
    "cancel my post",
    "cancel my listing",
    "cancel my offer",
    "me retracto",
    "me retracte",
    "me retracté",
    "cancelada",
    "cancelado",
)


KNOWN_UK_LOCATION_ALIASES = {
    "Leeds": ("leeds",),
    "Leeds City Centre": (
        "leeds city centre",
        "leeds city center",
        "city centre leeds",
        "city center leeds",
        "centro de leeds",
        "centro de la ciudad de leeds",
    ),
    "Headingley": ("headingley",),
    "Hyde Park": ("hyde park",),
    "Roundhay": ("roundhay",),
    "Manchester": ("manchester",),
    "Manchester City Centre": (
        "manchester city centre",
        "manchester city center",
        "city centre manchester",
        "city center manchester",
        "centro de manchester",
        "centro de la ciudad de manchester",
    ),
    "London": ("london", "londres"),
    "York": ("york",),
    "Birmingham": ("birmingham",),
    "Liverpool": ("liverpool",),
    "Sheffield": ("sheffield",),
    "Bradford": ("bradford",),
    "Bristol": ("bristol",),
    "Edinburgh": ("edinburgh", "edimburgo"),
    "Glasgow": ("glasgow",),
    "Newcastle": ("newcastle", "newcastle upon tyne"),
    "Nottingham": ("nottingham",),
    "Leicester": ("leicester",),
    "Coventry": ("coventry",),
    "Cardiff": ("cardiff",),
    "Belfast": ("belfast",),
    "Oxford": ("oxford",),
    "Cambridge": ("cambridge",),
    "Southampton": ("southampton",),
    "Portsmouth": ("portsmouth",),
    "Brighton": ("brighton", "brighton and hove"),
}
KNOWN_LOCATION_LOOKUP = {
    _normalize_lookup_text(alias): canonical
    for canonical, aliases in KNOWN_UK_LOCATION_ALIASES.items()
    for alias in aliases
}
KNOWN_LOCATION_ALIASES_SORTED = sorted(KNOWN_LOCATION_LOOKUP.items(), key=lambda item: len(item[0]), reverse=True)
KNOWN_EXCHANGE_CITY_BY_LOCATION = {
    "Leeds": "Leeds",
    "Leeds City Centre": "Leeds",
    "Headingley": "Leeds",
    "Hyde Park": "Leeds",
    "Roundhay": "Leeds",
    "Manchester": "Manchester",
    "Manchester City Centre": "Manchester",
    "London": "London",
    "York": "York",
    "Birmingham": "Birmingham",
    "Liverpool": "Liverpool",
    "Sheffield": "Sheffield",
    "Bradford": "Bradford",
    "Bristol": "Bristol",
    "Edinburgh": "Edinburgh",
    "Glasgow": "Glasgow",
    "Newcastle": "Newcastle",
    "Nottingham": "Nottingham",
    "Leicester": "Leicester",
    "Coventry": "Coventry",
    "Cardiff": "Cardiff",
    "Belfast": "Belfast",
    "Oxford": "Oxford",
    "Cambridge": "Cambridge",
    "Southampton": "Southampton",
    "Portsmouth": "Portsmouth",
    "Brighton": "Brighton",
}


class MessageRouter:
    """Route inbound WhatsApp text into the correct bot flow."""

    def __init__(
        self,
        *,
        settings: Settings,
        conversation_state_service: ConversationStateService,
        exchange_service: ExchangeService,
        listing_service: ListingService,
        event_service: EventService,
        summary_service: SummaryService,
        intent_classifier: IntentClassifier | None = None,
        llm_provider: LLMProvider | None = None,
    ) -> None:
        self.settings = settings
        self.conversation_state_service = conversation_state_service
        self.exchange_service = exchange_service
        self.listing_service = listing_service
        self.event_service = event_service
        self.summary_service = summary_service
        self.intent_classifier = intent_classifier
        self.llm_provider = llm_provider

    async def route_message(self, *, user: User, message_text: str) -> BotRouteResult:
        """Route a single inbound message."""

        state = await self.conversation_state_service.get_state(user.id)
        reply_language = self._resolve_reply_language(
            message_text,
            previous_message=state.last_user_message if state else None,
            state_language=state.draft_data.get("_reply_language") if state else None,
        )
        normalized = self._normalize_text(message_text)
        if normalized in {"cancel", "stop", "reset"}:
            await self.conversation_state_service.clear_state(user.id)
            return BotRouteResult(
                reply_text=self._translate(
                    reply_language,
                    en="Okay, I cleared your current draft. Send a new message whenever you are ready.",
                    es="Vale, he borrado tu borrador actual. Enviame un mensaje nuevo cuando quieras.",
                ),
                intent=IntentType.HELP_MENU,
            )

        if any(keyword in normalized for keyword in HELP_KEYWORDS):
            return self._build_menu_result(language=reply_language)

        publication_status = self._detect_publication_status(normalized)
        if publication_status and (state is None or state.current_flow == ConversationFlow.IDLE):
            status, publication_kind = publication_status
            return await self._handle_publication_status_update(
                user=user,
                status=status,
                publication_kind=publication_kind,
                message_text=message_text,
                reply_language=reply_language,
            )

        if state and state.current_flow != ConversationFlow.IDLE:
            return await self._continue_existing_flow(
                user,
                message_text,
                state.draft_data,
                state.current_flow,
                state.current_step,
                reply_language,
            )

        intent_result = await self._classify_intent(message_text)
        if intent_result.intent == IntentType.HELP_MENU:
            return self._build_menu_result(language=reply_language)
        if intent_result.intent == IntentType.SUMMARY:
            return BotRouteResult(
                reply_text=await self.summary_service.render_compact_text(language=reply_language),
                intent=IntentType.SUMMARY,
            )
        if intent_result.intent == IntentType.CREATE_EXCHANGE_OFFER:
            return await self._handle_exchange_create(user, message_text, {}, reply_language=reply_language)
        if intent_result.intent == IntentType.SEARCH_EXCHANGE_OFFERS:
            return await self._handle_exchange_search(user, message_text, {}, reply_language=reply_language)
        if intent_result.intent == IntentType.CREATE_LISTING:
            return await self._handle_listing_create(user, message_text, {}, reply_language=reply_language)
        if intent_result.intent == IntentType.SEARCH_LISTINGS:
            return await self._handle_listing_search(message_text, reply_language=reply_language)
        if intent_result.intent == IntentType.CREATE_EVENT:
            return await self._handle_event_create(user, message_text, {}, reply_language=reply_language)

        return self._build_menu_result(
            self._translate(
                reply_language,
                en="I did not fully understand that, but I can still help. Here are the main things I can do:",
                es="No he entendido del todo tu mensaje, pero aun asi puedo ayudarte. Estas son las cosas principales que puedo hacer:",
            ),
            language=reply_language,
        )

    async def _continue_existing_flow(
        self,
        user: User,
        message_text: str,
        draft_data: dict[str, Any],
        flow: ConversationFlow,
        current_step: str | None,
        reply_language: str,
    ) -> BotRouteResult:
        if flow == ConversationFlow.EXCHANGE_CREATE:
            return await self._handle_exchange_create(
                user,
                message_text,
                draft_data,
                current_step,
                reply_language=reply_language,
            )
        if flow == ConversationFlow.EXCHANGE_SEARCH:
            return await self._handle_exchange_search(
                user,
                message_text,
                draft_data,
                current_step,
                reply_language=reply_language,
            )
        if flow == ConversationFlow.LISTING_CREATE:
            return await self._handle_listing_create(
                user,
                message_text,
                draft_data,
                current_step,
                reply_language=reply_language,
            )
        if flow == ConversationFlow.EVENT_CREATE:
            return await self._handle_event_create(
                user,
                message_text,
                draft_data,
                current_step,
                reply_language=reply_language,
            )
        return self._build_menu_result(language=reply_language)

    async def _classify_intent(self, message_text: str) -> IntentResult:
        normalized = self._normalize_text(message_text)
        currency_count = len(self._extract_currency_mentions(message_text))

        if any(keyword in normalized for keyword in HELP_KEYWORDS):
            return IntentResult(intent=IntentType.HELP_MENU, confidence=0.99)
        if any(keyword in normalized for keyword in SUMMARY_KEYWORDS):
            return IntentResult(intent=IntentType.SUMMARY, confidence=0.95)
        if normalized in SELL_COMMANDS or normalized.startswith("sell "):
            return IntentResult(intent=IntentType.CREATE_LISTING, confidence=0.95)
        if any(marker in normalized for marker in LISTING_CREATE_MARKERS):
            return IntentResult(intent=IntentType.CREATE_LISTING, confidence=0.9)
        if any(marker in normalized for marker in LISTING_SEARCH_MARKERS):
            return IntentResult(intent=IntentType.SEARCH_LISTINGS, confidence=0.85)
        if "listing" in normalized and any(marker in normalized for marker in SEARCH_MARKERS):
            return IntentResult(intent=IntentType.SEARCH_LISTINGS, confidence=0.8)
        if any(keyword in normalized for keyword in EXCHANGE_KEYWORDS) or currency_count >= 2:
            if any(marker in normalized for marker in SEARCH_MARKERS):
                return IntentResult(intent=IntentType.SEARCH_EXCHANGE_OFFERS, confidence=0.87)
            return IntentResult(intent=IntentType.CREATE_EXCHANGE_OFFER, confidence=0.84)
        if self._looks_like_event(message_text):
            return IntentResult(intent=IntentType.CREATE_EVENT, confidence=0.82)

        if self.intent_classifier:
            try:
                embedding_result = await self.intent_classifier.classify_intent(message_text)
                if embedding_result.intent != IntentType.UNKNOWN:
                    return embedding_result
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.warning("Embedding intent classification failed: %s", exc)

        if self.llm_provider:
            try:
                llm_result = await self.llm_provider.classify_intent(message_text, context={})
                return llm_result
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.warning("LLM intent classification failed: %s", exc)

        return IntentResult(intent=IntentType.UNKNOWN, confidence=0.0)

    async def _handle_exchange_create(
        self,
        user: User,
        message_text: str,
        existing_draft: dict[str, Any],
        current_step: str | None = None,
        *,
        reply_language: str,
    ) -> BotRouteResult:
        data = await self._extract_data(
            IntentType.CREATE_EXCHANGE_OFFER,
            message_text,
            existing_draft,
            current_step=current_step,
        )
        if data.get("want_currencies") and not data.get("want_currency"):
            data["want_currency"] = data["want_currencies"][0]
        if not data.get("location"):
            known_city = await self._infer_known_exchange_city(user.id)
            if known_city:
                data["location"] = known_city
        missing_fields = [field for field in ("offer_currency", "want_currency", "amount", "location") if not data.get(field)]
        if missing_fields:
            next_field = missing_fields[0]
            await self.conversation_state_service.save_state(
                user_id=user.id,
                current_flow=ConversationFlow.EXCHANGE_CREATE,
                current_step=next_field,
                draft_data={**data, "_reply_language": reply_language},
                last_user_message=message_text,
            )
            return BotRouteResult(
                reply_text=self._follow_up_question(
                    IntentType.CREATE_EXCHANGE_OFFER,
                    next_field,
                    reply_language,
                    data=data,
                ),
                intent=IntentType.CREATE_EXCHANGE_OFFER,
            )

        payload = ExchangeOfferCreate(
            user_id=user.id,
            offer_currency=data["offer_currency"],
            want_currency=data["want_currency"],
            want_currencies=data.get("want_currencies", [data["want_currency"]]),
            amount=data["amount"],
            location=data.get("location"),
            notes=data.get("notes"),
        )
        offer = await self.exchange_service.create_offer(payload)
        matches = await self.exchange_service.find_ranked_matches(offer)
        await self.conversation_state_service.clear_state(user.id)
        reply_lines = [
            (
                self._translate(
                    reply_language,
                    en=(
                        f"I have posted your exchange offer: {offer.amount} {offer.offer_currency} "
                        f"for {self._format_currency_preferences(self.exchange_service.get_target_currencies(offer), language=reply_language)}"
                    ),
                    es=(
                        f"He publicado tu oferta de cambio: {offer.amount} {offer.offer_currency} "
                        f"por {self._format_currency_preferences(self.exchange_service.get_target_currencies(offer), language=reply_language)}"
                    ),
                )
                + self._translate(
                    reply_language,
                    en=f" in {offer.location}." if offer.location else ".",
                    es=f" en {offer.location}." if offer.location else ".",
                )
            )
        ]
        if matches:
            reply_lines.append(
                self._translate(
                    reply_language,
                    en="These active matches look closest right now:",
                    es="Estos matches activos son los mas cercanos ahora mismo:",
                )
            )
            for match in matches[:3]:
                reply_lines.append(
                    self._translate(
                        reply_language,
                        en=(
                            f"- {match.offer.amount} {match.offer.offer_currency} for "
                            f"{self._format_currency_preferences(self.exchange_service.get_target_currencies(match.offer), language=reply_language)}"
                            + (f" in {match.offer.location}" if match.offer.location else "")
                            + f" ({match.rank_reason})"
                        ),
                        es=(
                            f"- {match.offer.amount} {match.offer.offer_currency} por "
                            f"{self._format_currency_preferences(self.exchange_service.get_target_currencies(match.offer), language=reply_language)}"
                            + (f" en {match.offer.location}" if match.offer.location else "")
                            + f" ({match.rank_reason})"
                        ),
                    )
                )
        else:
            reply_lines.append(
                self._translate(
                    reply_language,
                    en="I do not see a reciprocal active match yet, but I will keep this offer available.",
                    es="Todavia no veo un match reciproco activo, pero dejare esta oferta disponible.",
                )
            )

        return BotRouteResult(
            reply_text="\n".join(reply_lines),
            intent=IntentType.CREATE_EXCHANGE_OFFER,
            metadata={
                "exchange_offer_id": offer.id,
                "match_count": len(matches),
                "matched_offer_ids": [match.offer.id for match in matches[:3]],
            },
        )

    async def _handle_exchange_search(
        self,
        user: User,
        message_text: str,
        existing_draft: dict[str, Any],
        current_step: str | None = None,
        *,
        reply_language: str,
    ) -> BotRouteResult:
        data = await self._extract_data(
            IntentType.SEARCH_EXCHANGE_OFFERS,
            message_text,
            existing_draft,
            current_step=current_step,
        )
        if not data.get("offer_currency") and not data.get("want_currency"):
            await self.conversation_state_service.save_state(
                user_id=user.id,
                current_flow=ConversationFlow.EXCHANGE_SEARCH,
                current_step="currency_pair",
                draft_data={**data, "_reply_language": reply_language},
                last_user_message=message_text,
            )
            return BotRouteResult(
                reply_text=self._translate(
                    reply_language,
                    en="Which currencies are you looking for? For example: pounds to euros.",
                    es="Que monedas estas buscando? Por ejemplo: libras por euros.",
                ),
                intent=IntentType.SEARCH_EXCHANGE_OFFERS,
            )

        offers = await self.exchange_service.search_offers(
            offer_currency=data.get("offer_currency"),
            want_currency=data.get("want_currency"),
            location=data.get("location"),
        )
        await self.conversation_state_service.clear_state(user.id)
        if not offers:
            return BotRouteResult(
                reply_text=self._translate(
                    reply_language,
                    en="I could not find any active exchange offers matching that request right now.",
                    es="No he encontrado ofertas de cambio activas que encajen con esa solicitud ahora mismo.",
                ),
                intent=IntentType.SEARCH_EXCHANGE_OFFERS,
            )

        lines = [
            self._translate(
                reply_language,
                en="Here are the closest exchange offers:",
                es="Estas son las ofertas de cambio que he encontrado:",
            )
        ]
        for item in offers[:5]:
            line = self._translate(
                reply_language,
                en=(
                    f"- {item.amount} {item.offer_currency} to "
                    f"{self._format_currency_preferences(self.exchange_service.get_target_currencies(item), language=reply_language)}"
                ),
                es=(
                    f"- {item.amount} {item.offer_currency} por "
                    f"{self._format_currency_preferences(self.exchange_service.get_target_currencies(item), language=reply_language)}"
                ),
            )
            if item.location:
                line += self._translate(
                    reply_language,
                    en=f" in {item.location}",
                    es=f" en {item.location}",
                )
            lines.append(line)
        return BotRouteResult(
            reply_text="\n".join(lines),
            intent=IntentType.SEARCH_EXCHANGE_OFFERS,
        )

    async def _handle_listing_create(
        self,
        user: User,
        message_text: str,
        existing_draft: dict[str, Any],
        current_step: str | None = None,
        *,
        reply_language: str,
    ) -> BotRouteResult:
        data = await self._extract_data(
            IntentType.CREATE_LISTING,
            message_text,
            existing_draft,
            current_step=current_step,
        )
        missing_fields = [field for field in ("title", "price", "location") if not data.get(field)]
        if missing_fields:
            next_field = missing_fields[0]
            await self.conversation_state_service.save_state(
                user_id=user.id,
                current_flow=ConversationFlow.LISTING_CREATE,
                current_step=next_field,
                draft_data={**data, "_reply_language": reply_language},
                last_user_message=message_text,
            )
            return BotRouteResult(
                reply_text=self._follow_up_question(IntentType.CREATE_LISTING, next_field, reply_language),
                intent=IntentType.CREATE_LISTING,
            )

        payload = ListingCreate(
            user_id=user.id,
            category=ListingCategory.ITEM,
            title=data["title"],
            description=data.get("description"),
            price=data["price"],
            currency=data.get("currency", "GBP"),
            location=data.get("location"),
        )
        listing = await self.listing_service.create_listing(payload)
        await self.conversation_state_service.clear_state(user.id)
        return BotRouteResult(
            reply_text=(
                self._translate(
                    reply_language,
                    en=f"I have posted your listing for {listing.title} at {listing.price} {listing.currency}",
                    es=f"He publicado tu anuncio de {listing.title} por {listing.price} {listing.currency}",
                )
                + self._translate(
                    reply_language,
                    en=f" in {listing.location}." if listing.location else ".",
                    es=f" en {listing.location}." if listing.location else ".",
                )
            ),
            intent=IntentType.CREATE_LISTING,
            metadata={"listing_id": listing.id},
        )

    async def _handle_listing_search(self, message_text: str, *, reply_language: str) -> BotRouteResult:
        data = self._extract_listing_search_data(message_text)
        listings = await self.listing_service.list_listings(
            location=data.get("location"),
            search_text=data.get("search_text"),
            active_only=True,
            limit=self.settings.default_summary_limit,
            offset=0,
        )
        if not listings:
            return BotRouteResult(
                reply_text=self._translate(
                    reply_language,
                    en="I could not find any active listings matching that search.",
                    es="No he encontrado anuncios activos que coincidan con esa busqueda.",
                ),
                intent=IntentType.SEARCH_LISTINGS,
            )

        lines = [
            self._translate(
                reply_language,
                en="Here are the latest listings:",
                es="Estos son los anuncios mas recientes:",
            )
        ]
        for item in listings[:5]:
            line = self._translate(
                reply_language,
                en=f"- {item.title} for {item.price} {item.currency}",
                es=f"- {item.title} por {item.price} {item.currency}",
            )
            if item.location:
                line += self._translate(
                    reply_language,
                    en=f" in {item.location}",
                    es=f" en {item.location}",
                )
            lines.append(line)
        return BotRouteResult(reply_text="\n".join(lines), intent=IntentType.SEARCH_LISTINGS)

    async def _handle_event_create(
        self,
        user: User,
        message_text: str,
        existing_draft: dict[str, Any],
        current_step: str | None = None,
        *,
        reply_language: str,
    ) -> BotRouteResult:
        data = await self._extract_data(
            IntentType.CREATE_EVENT,
            message_text,
            existing_draft,
            current_step=current_step,
        )
        missing_fields = [field for field in ("title", "event_date", "location") if not data.get(field)]
        if missing_fields:
            next_field = missing_fields[0]
            await self.conversation_state_service.save_state(
                user_id=user.id,
                current_flow=ConversationFlow.EVENT_CREATE,
                current_step=next_field,
                draft_data={**data, "_reply_language": reply_language},
                last_user_message=message_text,
            )
            return BotRouteResult(
                reply_text=self._follow_up_question(IntentType.CREATE_EVENT, next_field, reply_language),
                intent=IntentType.CREATE_EVENT,
            )

        payload = CommunityEventCreate(
            user_id=user.id,
            title=data["title"],
            description=data.get("description"),
            event_date=data["event_date"],
            location=data.get("location"),
        )
        event = await self.event_service.create_event(payload)
        await self.conversation_state_service.clear_state(user.id)
        return BotRouteResult(
            reply_text=(
                self._translate(
                    reply_language,
                    en=f"I have posted your event: {event.title} on {self._format_event_datetime(event.event_date, reply_language)}",
                    es=f"He publicado tu evento: {event.title} el {self._format_event_datetime(event.event_date, reply_language)}",
                )
                + self._translate(
                    reply_language,
                    en=f" in {event.location}." if event.location else ".",
                    es=f" en {event.location}." if event.location else ".",
                )
            ),
            intent=IntentType.CREATE_EVENT,
            metadata={"event_id": event.id},
        )

    async def _extract_data(
        self,
        intent: IntentType,
        message_text: str,
        existing_draft: dict[str, Any],
        current_step: str | None = None,
    ) -> dict[str, Any]:
        rule_data = self._rule_extract(intent, message_text)
        step_data = (
            self._extract_active_flow_data(intent, current_step, message_text, existing_draft) if current_step else {}
        )
        if intent == IntentType.CREATE_EXCHANGE_OFFER and current_step == "want_currency":
            rule_data.pop("offer_currency", None)
            if step_data.get("want_currencies"):
                rule_data.pop("want_currency", None)
                rule_data.pop("want_currencies", None)
        if intent == IntentType.CREATE_EXCHANGE_OFFER and current_step == "offer_currency":
            rule_data.pop("want_currency", None)
            rule_data.pop("want_currencies", None)
        if current_step and "description" in existing_draft:
            rule_data.pop("description", None)
        if current_step and "notes" in existing_draft:
            rule_data.pop("notes", None)
        merged = {
            **existing_draft,
            **{key: value for key, value in rule_data.items() if value is not None},
            **{key: value for key, value in step_data.items() if value is not None},
        }

        should_try_llm = self.llm_provider is not None and not self._is_data_sufficient(intent, merged)
        if should_try_llm:
            try:
                llm_result = await self.llm_provider.extract_structured_data(
                    message_text,
                    context={
                        "draft_data": existing_draft,
                        "current_step": current_step,
                        "known_locations_hint": sorted(KNOWN_UK_LOCATION_ALIASES.keys()),
                    },
                    intent=intent,
                )
                merged = {
                    **llm_result.data,
                    **{key: value for key, value in merged.items() if value is not None},
                }
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.warning("LLM extraction failed for %s: %s", intent.value, exc)
        if intent == IntentType.CREATE_EXCHANGE_OFFER:
            merged = self._reconcile_exchange_draft(
                merged=merged,
                existing_draft=existing_draft,
                message_text=message_text,
                current_step=current_step,
            )
        return merged

    def _rule_extract(self, intent: IntentType, message_text: str) -> dict[str, Any]:
        if intent in {IntentType.CREATE_EXCHANGE_OFFER, IntentType.SEARCH_EXCHANGE_OFFERS}:
            return self._extract_exchange_data(message_text)
        if intent == IntentType.CREATE_LISTING:
            return self._extract_listing_data(message_text)
        if intent == IntentType.CREATE_EVENT:
            return self._extract_event_data(message_text)
        if intent == IntentType.SEARCH_LISTINGS:
            return self._extract_listing_search_data(message_text)
        return {}

    def _extract_exchange_data(self, message_text: str) -> dict[str, Any]:
        data: dict[str, Any] = {"notes": message_text}
        currencies = self._extract_currency_mentions(message_text)
        amount_match = AMOUNT_WITH_CURRENCY_PATTERN.search(message_text)
        offer_currency: str | None = None
        if amount_match:
            data["amount"] = self._safe_decimal(amount_match.group("amount"))
            offer_currency = self._normalize_currency(amount_match.group("currency"))
            data["offer_currency"] = offer_currency

        if len(currencies) == 1 and "offer_currency" not in data and "want_currency" not in data:
            currency = currencies[0]
            if self._looks_like_want_currency_fragment(message_text):
                data["want_currency"] = currency
                data["want_currencies"] = [currency]
            else:
                data["offer_currency"] = currency
        elif len(currencies) >= 2:
            if offer_currency is None and not self._looks_like_want_currency_fragment(message_text):
                offer_currency = currencies[0]
                data["offer_currency"] = offer_currency

            target_currencies = self._extract_exchange_target_currencies(
                message_text,
                offer_currency=offer_currency or data.get("offer_currency"),
            )
            if target_currencies:
                data["want_currency"] = target_currencies[0]
                data["want_currencies"] = target_currencies
            elif "offer_currency" not in data:
                data["offer_currency"] = currencies[0]

        data["location"] = self._normalize_exchange_location(self._extract_location(message_text))
        return {key: value for key, value in data.items() if value is not None}

    def _extract_listing_data(self, message_text: str) -> dict[str, Any]:
        data: dict[str, Any] = {"description": message_text}
        title_match = re.search(
            r"(?:i am selling|i'm selling|selling|for sale|vendo|estoy vendiendo|quiero vender|en venta)\s+(?:an?\s+|the\s+|un(?:a)?\s+|mi\s+)?(?P<title>.+?)(?:\s+(?:in|en)\s+|\s+(?:for|por)\s+\d|$)",
            message_text,
            re.IGNORECASE,
        )
        if title_match:
            data["title"] = title_match.group("title").strip(" .,!?")

        price_match = PRICE_PATTERN.search(message_text)
        if price_match:
            data["price"] = self._safe_decimal(price_match.group("amount"))
            currency_word = price_match.group("currency")
            data["currency"] = self._normalize_currency(currency_word) if currency_word else "GBP"

        data["location"] = self._extract_location(message_text)
        return {key: value for key, value in data.items() if value is not None}

    def _extract_active_flow_data(
        self,
        intent: IntentType,
        current_step: str,
        message_text: str,
        existing_draft: dict[str, Any],
    ) -> dict[str, Any]:
        cleaned = message_text.strip(" .,!?")
        if not cleaned:
            return {}

        if intent == IntentType.CREATE_LISTING:
            return self._extract_listing_active_flow_data(
                message_text,
                cleaned=cleaned,
                existing_draft=existing_draft,
                current_step=current_step,
            )

        if intent == IntentType.CREATE_EXCHANGE_OFFER:
            return self._extract_exchange_active_flow_data(
                message_text,
                cleaned=cleaned,
                existing_draft=existing_draft,
                current_step=current_step,
            )

        if intent == IntentType.SEARCH_EXCHANGE_OFFERS and current_step == "currency_pair":
            currencies = self._extract_currency_mentions(message_text)
            if len(currencies) >= 2:
                return {"offer_currency": currencies[0], "want_currency": currencies[1]}
            if len(currencies) == 1:
                return {"offer_currency": currencies[0]}

        if intent == IntentType.CREATE_EVENT:
            return self._extract_event_active_flow_data(
                message_text,
                cleaned=cleaned,
                existing_draft=existing_draft,
                current_step=current_step,
            )

        return {}

    def _extract_listing_active_flow_data(
        self,
        message_text: str,
        *,
        cleaned: str,
        existing_draft: dict[str, Any],
        current_step: str,
    ) -> dict[str, Any]:
        data: dict[str, Any] = {}

        if not existing_draft.get("price"):
            data.update(self._extract_listing_price_reply(message_text))
        if not existing_draft.get("location"):
            location = self._extract_location(message_text)
            if location:
                data["location"] = location
        if not existing_draft.get("title") and self._is_listing_title_candidate(
            cleaned,
            message_text=message_text,
            current_step=current_step,
            extracted_data=data,
        ):
            data["title"] = cleaned

        return data

    def _extract_exchange_active_flow_data(
        self,
        message_text: str,
        *,
        cleaned: str,
        existing_draft: dict[str, Any],
        current_step: str,
    ) -> dict[str, Any]:
        data: dict[str, Any] = {}

        amount = self._extract_decimal_reply(message_text)
        if amount is not None and not existing_draft.get("amount"):
            data["amount"] = amount

        currencies = self._extract_currency_mentions(message_text)
        if current_step == "want_currency" and existing_draft.get("offer_currency"):
            target_currencies = self._extract_exchange_target_currencies(
                message_text,
                offer_currency=existing_draft.get("offer_currency"),
            )
            if target_currencies:
                existing_targets = self._normalize_currency_list(existing_draft.get("want_currencies") or [])
                merged_targets = self._normalize_currency_list(existing_targets + target_currencies)
                data["want_currency"] = merged_targets[0]
                data["want_currencies"] = merged_targets
        elif len(currencies) >= 2:
            if not existing_draft.get("offer_currency"):
                data["offer_currency"] = currencies[0]
            target_currencies = self._extract_exchange_target_currencies(
                message_text,
                offer_currency=data.get("offer_currency") or existing_draft.get("offer_currency"),
            )
            if target_currencies and not existing_draft.get("want_currency"):
                data["want_currency"] = target_currencies[0]
                data["want_currencies"] = target_currencies
        elif len(currencies) == 1:
            currency = currencies[0]
            if current_step == "want_currency" and not existing_draft.get("want_currency"):
                data["want_currency"] = currency
                data["want_currencies"] = [currency]
            elif current_step == "offer_currency" and not existing_draft.get("offer_currency"):
                data["offer_currency"] = currency
            elif not existing_draft.get("offer_currency"):
                data["offer_currency"] = currency
            elif not existing_draft.get("want_currency") and currency != existing_draft.get("offer_currency"):
                data["want_currency"] = currency
                data["want_currencies"] = [currency]

        if not existing_draft.get("location"):
            location = self._normalize_exchange_location(self._extract_location(message_text))
            if location:
                data["location"] = location

        if not existing_draft.get("notes") and not data and self._is_free_text_candidate(cleaned):
            data["notes"] = cleaned

        return data

    def _reconcile_exchange_draft(
        self,
        *,
        merged: dict[str, Any],
        existing_draft: dict[str, Any],
        message_text: str,
        current_step: str | None,
    ) -> dict[str, Any]:
        draft = dict(merged)
        explicit_offer_currency = self._extract_explicit_offer_currency(message_text)
        explicit_want_currencies = self._extract_explicit_want_currencies(
            message_text,
            offer_currency=explicit_offer_currency or draft.get("offer_currency"),
        )
        has_amount_in_message = self._extract_decimal_reply(message_text) is not None
        offer_cleared_by_correction = False
        want_cleared_by_correction = False

        if explicit_want_currencies:
            draft["want_currency"] = explicit_want_currencies[0]
            draft["want_currencies"] = explicit_want_currencies
            if existing_draft.get("offer_currency") == explicit_want_currencies[0]:
                draft.pop("offer_currency", None)
                offer_cleared_by_correction = True
                if not has_amount_in_message:
                    draft.pop("amount", None)
        elif (
            current_step not in {"want_currency"}
            and existing_draft.get("want_currency")
            and draft.get("want_currency") != existing_draft.get("want_currency")
        ):
            draft["want_currency"] = existing_draft["want_currency"]
            existing_targets = self._normalize_currency_list(existing_draft.get("want_currencies") or [])
            if existing_targets:
                draft["want_currencies"] = existing_targets

        if explicit_offer_currency:
            if existing_draft.get("offer_currency") and explicit_offer_currency != existing_draft.get("offer_currency"):
                draft.pop("amount", None)
            draft["offer_currency"] = explicit_offer_currency
            if draft.get("want_currency") == explicit_offer_currency and not explicit_want_currencies:
                draft.pop("want_currency", None)
                draft.pop("want_currencies", None)
                want_cleared_by_correction = True
        elif (
            not offer_cleared_by_correction
            and not want_cleared_by_correction
            and
            current_step not in {"offer_currency"}
            and existing_draft.get("offer_currency")
            and draft.get("offer_currency") != existing_draft.get("offer_currency")
        ):
            draft["offer_currency"] = existing_draft["offer_currency"]

        if draft.get("want_currencies") and draft.get("want_currency") not in draft["want_currencies"]:
            draft["want_currency"] = draft["want_currencies"][0]
        if draft.get("want_currency") and not draft.get("want_currencies"):
            draft["want_currencies"] = [draft["want_currency"]]
        return draft

    def _extract_event_active_flow_data(
        self,
        message_text: str,
        *,
        cleaned: str,
        existing_draft: dict[str, Any],
        current_step: str,
    ) -> dict[str, Any]:
        data: dict[str, Any] = {}

        if not existing_draft.get("event_date"):
            event_date = self._parse_event_date(message_text)
            if event_date is not None:
                data["event_date"] = event_date

        if not existing_draft.get("location"):
            location = self._extract_location(message_text)
            if location:
                data["location"] = location

        if not existing_draft.get("title") and self._is_event_title_candidate(
            cleaned,
            message_text=message_text,
            current_step=current_step,
            extracted_data=data,
        ):
            data["title"] = cleaned

        return data

    def _extract_listing_price_reply(self, message_text: str) -> dict[str, Any]:
        amount = self._extract_decimal_reply(message_text)
        if amount is None:
            return {}

        currencies = self._extract_currency_mentions(message_text)
        currency = currencies[0] if currencies else "GBP"
        return {"price": amount, "currency": currency}

    def _is_listing_title_candidate(
        self,
        cleaned: str,
        *,
        message_text: str,
        current_step: str,
        extracted_data: dict[str, Any],
    ) -> bool:
        normalized = self._normalize_text(cleaned)
        if len(cleaned) < 2:
            return False
        if extracted_data.get("price") is not None or extracted_data.get("location"):
            return False
        if normalized in SELL_COMMANDS or normalized in LISTING_CREATE_MARKERS:
            return False
        if any(marker in normalized for marker in LISTING_CREATE_MARKERS):
            return False
        if self._extract_location(message_text):
            return False
        if self._extract_decimal_reply(message_text) is not None:
            return False
        return self._is_free_text_candidate(cleaned)

    def _is_event_title_candidate(
        self,
        cleaned: str,
        *,
        message_text: str,
        current_step: str,
        extracted_data: dict[str, Any],
    ) -> bool:
        if extracted_data.get("event_date") is not None or extracted_data.get("location"):
            return False
        if self._parse_event_date(message_text) is not None:
            return False
        if self._extract_location(message_text):
            return False
        return self._is_free_text_candidate(cleaned)

    def _is_free_text_candidate(self, cleaned: str) -> bool:
        normalized = self._normalize_text(cleaned)
        if len(cleaned) < 2:
            return False
        if normalized in HELP_KEYWORDS or normalized in SUMMARY_KEYWORDS:
            return False
        if normalized in SELL_COMMANDS:
            return False
        return True

    def _extract_listing_search_data(self, message_text: str) -> dict[str, Any]:
        location = self._extract_location(message_text)
        cleaned = re.sub(
            r"\b(show me|find|search|browse|listings?|items?|muestrame|muestame|buscar|busca|ver|anuncios?|publicaciones?)\b",
            "",
            message_text,
            flags=re.IGNORECASE,
        )
        if location:
            cleaned = re.sub(rf"\b(?:in|en)\s+{re.escape(location)}\b", "", cleaned, flags=re.IGNORECASE)
        search_text = cleaned.strip(" .!?")
        data: dict[str, Any] = {}
        if location:
            data["location"] = location
        if search_text and len(search_text) > 2:
            data["search_text"] = search_text
        return data

    def _extract_event_data(self, message_text: str) -> dict[str, Any]:
        cleaned = re.sub(
            r"^(there is|there's|there will be|event:?|community event:?|join us for|hay|habra|habrá|evento:?|evento comunitario:?|unete a)\s+",
            "",
            message_text,
            flags=re.IGNORECASE,
        ).strip()
        title = re.split(r"\b(?:on|at|in|el|a las|en)\b", cleaned, maxsplit=1, flags=re.IGNORECASE)[0].strip(" .,!?")
        if title.lower().startswith(("a ", "an ", "the ")):
            title = re.sub(r"^(a|an|the)\s+", "", title, flags=re.IGNORECASE)
        event_date = self._parse_event_date(message_text)
        location = self._extract_location(message_text)
        data = {
            "title": title if title else None,
            "description": message_text,
            "event_date": event_date,
            "location": location,
        }
        return {key: value for key, value in data.items() if value is not None}

    def _extract_currency_mentions(self, message_text: str) -> list[str]:
        seen: list[str] = []
        for match in CURRENCY_WORD_PATTERN.finditer(message_text):
            normalized = self._normalize_currency(match.group(0))
            if normalized and normalized not in seen:
                seen.append(normalized)
        return seen

    def _extract_exchange_target_currencies(
        self,
        message_text: str,
        *,
        offer_currency: str | None = None,
    ) -> list[str]:
        currencies = self._extract_currency_mentions(message_text)
        targets = currencies
        if offer_currency:
            targets = [currency for currency in currencies if currency != offer_currency]
        if self._looks_like_want_currency_fragment(message_text):
            return self._normalize_currency_list(targets or currencies)
        return self._normalize_currency_list(targets)

    def _normalize_currency_list(self, currencies: list[str]) -> list[str]:
        normalized: list[str] = []
        for currency in currencies:
            upper_currency = (currency or "").strip().upper()
            if upper_currency and upper_currency not in normalized:
                normalized.append(upper_currency)
        return normalized

    def _extract_explicit_offer_currency(self, message_text: str) -> str | None:
        normalized = self._normalize_text(message_text)
        if not re.search(r"\b(?:tengo|ofrezco|i have|i've got|ive got|have|offering|vendo)\b", normalized):
            return None

        currencies = self._extract_currency_mentions(message_text)
        if not currencies:
            return None
        return currencies[0]

    def _extract_explicit_want_currencies(
        self,
        message_text: str,
        *,
        offer_currency: str | None = None,
    ) -> list[str]:
        normalized = self._normalize_text(message_text)
        if not re.search(
            r"\b(?:quiero|busco|necesito|recibir|want|looking for|need|after)\b",
            normalized,
        ):
            return []

        currencies = self._extract_currency_mentions(message_text)
        if not currencies:
            return []

        if (
            len(currencies) == 1
            and self._extract_decimal_reply(message_text) is not None
            and not self._looks_like_want_currency_fragment(message_text)
        ):
            return []

        targets = self._extract_exchange_target_currencies(
            message_text,
            offer_currency=offer_currency,
        )
        if targets:
            return targets
        return self._normalize_currency_list(currencies)

    def _looks_like_want_currency_fragment(self, message_text: str) -> bool:
        normalized = self._normalize_text(message_text)
        return bool(
            re.match(r"^(?:for|por|to|a)\s+\w+", normalized)
            or "in return" in normalized
            or "a cambio" in normalized
            or "recibir" in normalized
        )

    @staticmethod
    def _normalize_currency(value: str) -> str | None:
        normalized_key = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii").strip().lower()
        normalized = CURRENCY_ALIASES.get(normalized_key)
        return normalized

    @staticmethod
    def _normalize_text(message_text: str) -> str:
        normalized = unicodedata.normalize("NFKD", message_text)
        ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
        return " ".join(ascii_text.lower().strip().split())

    def _extract_location(self, message_text: str) -> str | None:
        explicit_match = re.search(
            r"\b(?:in|en|at|near|cerca de)\s+([A-Za-z][A-Za-z\s'-]{1,80})",
            message_text,
            re.IGNORECASE,
        )
        if explicit_match:
            candidate = explicit_match.group(1).strip(" .,!?")
            if not any(character.isdigit() for character in candidate):
                return self._canonicalize_location(candidate)

        standalone_location = self._match_known_location(message_text)
        if standalone_location:
            return standalone_location
        return None

    def _normalize_exchange_location(self, location: str | None) -> str | None:
        if location is None:
            return None

        canonical = self._canonicalize_location(location)
        return KNOWN_EXCHANGE_CITY_BY_LOCATION.get(canonical, canonical)

    def _canonicalize_location(self, candidate: str) -> str:
        known_location = self._match_known_location(candidate, allow_partial=True)
        if known_location:
            return known_location
        return candidate.strip(" .,!?")

    def _match_known_location(self, message_text: str, *, allow_partial: bool = False) -> str | None:
        normalized = self._normalize_text(message_text)
        exact_match = KNOWN_LOCATION_LOOKUP.get(normalized)
        if exact_match:
            return exact_match

        if allow_partial:
            for alias, canonical in KNOWN_LOCATION_ALIASES_SORTED:
                if re.search(rf"\b{re.escape(alias)}\b", normalized):
                    return canonical
        return None

    def _parse_event_date(self, message_text: str) -> datetime | None:
        timezone_name = self.settings.business_timezone
        candidate_fragments: list[str] = []
        fragment_match = re.search(
            r"\b(?:on|at|el|a las)\s+(.+?)(?:\s+(?:in|en)\s+[A-Za-z][A-Za-z\s'-]{1,80})?$",
            message_text,
            re.IGNORECASE,
        )
        if fragment_match:
            candidate_fragments.append(fragment_match.group(1).strip(" .,!?"))
        candidate_fragments.append(message_text)

        parser_settings = {
            "TIMEZONE": timezone_name,
            "TO_TIMEZONE": timezone_name,
            "RETURN_AS_TIMEZONE_AWARE": True,
            "PREFER_DATES_FROM": "future",
        }

        for candidate in candidate_fragments:
            parsed = dateparser.parse(candidate, settings=parser_settings)
            if parsed is not None:
                return parsed.astimezone(ZoneInfo("UTC"))
        return None

    @staticmethod
    def _safe_decimal(value: str | None) -> Decimal | None:
        if value is None:
            return None
        try:
            return Decimal(value)
        except (InvalidOperation, ValueError):
            return None

    def _extract_decimal_reply(self, message_text: str) -> Decimal | None:
        amount_match = re.search(r"(?P<amount>\d+(?:\.\d+)?)", message_text)
        if amount_match is None:
            return None
        return self._safe_decimal(amount_match.group("amount"))

    def _looks_like_event(self, message_text: str) -> bool:
        normalized = self._normalize_text(message_text)
        if any(keyword in normalized for keyword in EVENT_KEYWORDS):
            return True
        return any(day in normalized for day in DAY_KEYWORDS) and self._parse_event_date(message_text) is not None

    @staticmethod
    def _translate(language: str, *, en: str, es: str) -> str:
        return en if language == "en" else es

    def _detect_message_language(self, message_text: str) -> str | None:
        normalized = self._normalize_text(message_text)
        if not normalized:
            return None

        tokens = set(normalized.split())
        english_score = 0
        spanish_score = 0

        english_score += sum(2 for phrase in ENGLISH_LANGUAGE_PHRASES if phrase in normalized)
        spanish_score += sum(2 for phrase in SPANISH_LANGUAGE_PHRASES if phrase in normalized)
        english_score += sum(2 for word in ENGLISH_LANGUAGE_WORDS if word in tokens)
        spanish_score += sum(2 for word in SPANISH_LANGUAGE_WORDS if word in tokens)

        if any(character in message_text for character in SPANISH_LANGUAGE_HINTS):
            spanish_score += 2

        if english_score == spanish_score:
            return None

        winner = "en" if english_score > spanish_score else "es"
        winning_score = max(english_score, spanish_score)
        losing_score = min(english_score, spanish_score)
        if winning_score < 2 or winning_score - losing_score < 1:
            return None
        return winner

    def _resolve_reply_language(
        self,
        message_text: str,
        *,
        previous_message: str | None = None,
        state_language: str | None = None,
    ) -> str:
        detected = self._detect_message_language(message_text)
        if detected:
            return detected
        if state_language in {"en", "es"}:
            return state_language
        if previous_message:
            detected_previous = self._detect_message_language(previous_message)
            if detected_previous:
                return detected_previous
        return DEFAULT_REPLY_LANGUAGE

    @staticmethod
    def _format_event_datetime(event_date: datetime, language: str) -> str:
        if language == "en":
            return event_date.strftime("%a %d %b %H:%M")
        return event_date.strftime("%d/%m %H:%M")

    def _follow_up_question(
        self,
        intent: IntentType,
        field_name: str,
        language: str,
        *,
        data: dict[str, Any] | None = None,
    ) -> str:
        prompts = {
            IntentType.CREATE_EXCHANGE_OFFER: {
                "offer_currency": self._translate(
                    language,
                    en="Which currency do you want to offer?",
                    es="Que moneda quieres ofrecer?",
                ),
                "want_currency": self._translate(
                    language,
                    en="Which currency do you want in return?",
                    es="Que moneda quieres recibir a cambio?",
                ),
                "amount": self._translate(
                    language,
                    en="How much money do you want to exchange?",
                    es="Cuanto dinero quieres cambiar?",
                ),
                "location": self._translate(
                    language,
                    en="Which city are you in?",
                    es="En que ciudad estas?",
                ),
            },
            IntentType.CREATE_LISTING: {
                "title": self._translate(
                    language,
                    en="What item are you selling?",
                    es="Que articulo quieres vender?",
                ),
                "price": self._translate(
                    language,
                    en="What price would you like to post?",
                    es="Que precio quieres publicar?",
                ),
                "location": self._translate(
                    language,
                    en="Where is the item available?",
                    es="Donde esta disponible el articulo?",
                ),
            },
            IntentType.CREATE_EVENT: {
                "title": self._translate(
                    language,
                    en="What is the event title?",
                    es="Cual es el titulo del evento?",
                ),
                "event_date": self._translate(
                    language,
                    en="When is the event happening?",
                    es="Cuando es el evento?",
                ),
                "location": self._translate(
                    language,
                    en="Where is the event taking place?",
                    es="Donde sera el evento?",
                ),
            },
        }
        if intent == IntentType.CREATE_EXCHANGE_OFFER:
            contextual_prompt = self._build_exchange_follow_up_question(
                field_name=field_name,
                language=language,
                data=data or {},
            )
            if contextual_prompt:
                return contextual_prompt

        return prompts[intent][field_name]

    def _build_exchange_follow_up_question(
        self,
        *,
        field_name: str,
        language: str,
        data: dict[str, Any],
    ) -> str | None:
        amount = self._format_amount_for_reply(data.get("amount"))
        offer_currency = data.get("offer_currency")
        want_currencies = self._normalize_currency_list(
            list(data.get("want_currencies") or ([] if data.get("want_currency") is None else [data["want_currency"]]))
        )
        want_currency_text = self._format_currency_preferences(want_currencies, language=language) if want_currencies else None

        if field_name == "want_currency" and amount and offer_currency:
            return self._translate(
                language,
                en=(
                    f"Understood: you want to exchange {amount} {offer_currency}. "
                    "Which currency do you want in return?"
                ),
                es=(
                    f"Entendido: quieres cambiar {amount} {offer_currency}. "
                    "Que moneda quieres recibir a cambio?"
                ),
            )

        if field_name == "amount" and offer_currency and want_currency_text:
            return self._translate(
                language,
                en=(
                    f"Understood: you want to exchange {offer_currency} for {want_currency_text}. "
                    "How much money do you want to exchange?"
                ),
                es=(
                    f"Entendido: quieres cambiar {offer_currency} por {want_currency_text}. "
                    "Cuanto dinero quieres cambiar?"
                ),
            )

        if field_name == "location" and amount and offer_currency and want_currency_text:
            return self._translate(
                language,
                en=(
                    f"Understood: you want to exchange {amount} {offer_currency} for {want_currency_text}. "
                    "Which city are you in?"
                ),
                es=(
                    f"Entendido: quieres cambiar {amount} {offer_currency} por {want_currency_text}. "
                    "En que ciudad estas?"
                ),
            )

        return None

    def _format_amount_for_reply(self, value: Any) -> str | None:
        if value is None:
            return None

        if isinstance(value, Decimal):
            decimal_value = value
        else:
            decimal_value = self._safe_decimal(str(value))
            if decimal_value is None:
                return str(value)

        if decimal_value == decimal_value.to_integral():
            return format(decimal_value.quantize(Decimal("1")), "f")

        normalized = format(decimal_value.normalize(), "f").rstrip("0").rstrip(".")
        return normalized or "0"

    def _format_currency_preferences(self, currencies: list[str], *, language: str) -> str:
        normalized = self._normalize_currency_list(currencies)
        if not normalized:
            return ""
        if len(normalized) == 1:
            return normalized[0]
        separator = " or " if language == "en" else " o "
        return ", ".join(normalized[:-1]) + separator + normalized[-1]

    async def _infer_known_exchange_city(self, user_id: int) -> str | None:
        candidates: list[tuple[datetime, str]] = []
        for lookup in (
            self.exchange_service.get_latest_user_location,
            self.listing_service.get_latest_user_location,
            self.event_service.get_latest_user_location,
        ):
            candidate = await lookup(user_id)
            if candidate is None:
                continue

            created_at, location = candidate
            normalized_city = self._normalize_exchange_location(location)
            if normalized_city:
                candidates.append((created_at, normalized_city))

        if not candidates:
            return None

        candidates.sort(key=lambda item: item[0], reverse=True)
        return candidates[0][1]

    def _detect_publication_status(self, normalized_message: str) -> tuple[RecordStatus, str | None] | None:
        publication_kind = self._infer_publication_kind_from_text(normalized_message)
        if any(marker in normalized_message for marker in CANCELLED_MARKERS):
            return RecordStatus.CANCELLED, publication_kind
        if any(marker in normalized_message for marker in EXCHANGE_RESOLVED_MARKERS):
            return RecordStatus.RESOLVED, "exchange"
        if any(marker in normalized_message for marker in LISTING_RESOLVED_MARKERS):
            return RecordStatus.RESOLVED, "listing"
        if any(marker in normalized_message for marker in GENERIC_RESOLVED_MARKERS):
            return RecordStatus.RESOLVED, publication_kind
        return None

    def _infer_publication_kind_from_text(self, normalized_message: str) -> str | None:
        if any(
            keyword in normalized_message
            for keyword in (
                "cambi",
                "exchange",
                "cambio",
                "oferta",
                "ofertas",
                "divisa",
                "divisas",
            )
        ):
            return "exchange"
        if any(
            keyword in normalized_message
            for keyword in (
                "vend",
                "sell",
                "selling",
                "listing",
                "sale",
                "anuncio",
                "anuncios",
                "articulo",
                "articulos",
                "publicacion",
                "publicaciones",
            )
        ):
            return "listing"
        if any(
            keyword in normalized_message
            for keyword in ("event", "evento", "partido", "match", "meetup", "reunion", "taller")
        ):
            return "event"
        return None

    async def _handle_publication_status_update(
        self,
        *,
        user: User,
        status: RecordStatus,
        publication_kind: str | None,
        message_text: str,
        reply_language: str,
    ) -> BotRouteResult:
        candidates: list[tuple[str, Any]] = []
        exchange_offer = await self.exchange_service.get_latest_active_offer_for_user(user.id)
        if exchange_offer is not None:
            candidates.append(("exchange", exchange_offer))

        listing = await self.listing_service.get_latest_active_listing_for_user(user.id)
        if listing is not None:
            candidates.append(("listing", listing))

        event = await self.event_service.get_latest_active_event_for_user(user.id)
        if event is not None:
            candidates.append(("event", event))

        if publication_kind is not None:
            preferred_candidates = [candidate for candidate in candidates if candidate[0] == publication_kind]
            if preferred_candidates:
                candidates = preferred_candidates

        if not candidates:
            reply_text = self._translate(
                reply_language,
                en="I could not find any active post to update right now.",
                es="No he encontrado ninguna publicacion activa para actualizar ahora mismo.",
            )
            return BotRouteResult(reply_text=reply_text, intent=IntentType.UNKNOWN)

        candidates.sort(key=lambda item: item[1].created_at, reverse=True)
        selected_kind, record = candidates[0]

        if selected_kind == "exchange":
            await self.exchange_service.update_offer_status(record, status)
        elif selected_kind == "listing":
            await self.listing_service.update_listing_status(record, status)
        else:
            await self.event_service.update_event_status(record, status)

        if status == RecordStatus.RESOLVED:
            reply_text = self._translate(
                reply_language,
                en=self._resolved_status_reply(selected_kind),
                es=self._resolved_status_reply(selected_kind, language="es"),
            )
        else:
            reply_text = self._translate(
                reply_language,
                en=self._cancelled_status_reply(selected_kind),
                es=self._cancelled_status_reply(selected_kind, language="es"),
            )
        return BotRouteResult(reply_text=reply_text, intent=IntentType.UNKNOWN)

    def _resolved_status_reply(self, publication_kind: str, *, language: str = "en") -> str:
        if publication_kind == "exchange":
            return (
                "I have marked your latest exchange offer as resolved."
                if language == "en"
                else "He marcado tu ultima oferta de cambio como resuelta."
            )
        if publication_kind == "listing":
            return (
                "I have marked your latest listing as resolved."
                if language == "en"
                else "He marcado tu ultimo anuncio como resuelto."
            )
        return (
            "I have marked your latest event as resolved."
            if language == "en"
            else "He marcado tu ultimo evento como resuelto."
        )

    def _cancelled_status_reply(self, publication_kind: str, *, language: str = "en") -> str:
        if publication_kind == "exchange":
            return (
                "I have marked your latest exchange offer as cancelled."
                if language == "en"
                else "He marcado tu ultima oferta de cambio como cancelada."
            )
        if publication_kind == "listing":
            return (
                "I have marked your latest listing as cancelled."
                if language == "en"
                else "He marcado tu ultimo anuncio como cancelado."
            )
        return (
            "I have marked your latest event as cancelled."
            if language == "en"
            else "He marcado tu ultimo evento como cancelado."
        )

    def _is_data_sufficient(self, intent: IntentType, data: dict[str, Any]) -> bool:
        if intent == IntentType.CREATE_EXCHANGE_OFFER:
            return all(data.get(field) for field in ("offer_currency", "want_currency", "amount", "location"))
        if intent == IntentType.SEARCH_EXCHANGE_OFFERS:
            return bool(data.get("offer_currency") or data.get("want_currency"))
        if intent == IntentType.CREATE_LISTING:
            return all(data.get(field) for field in ("title", "price", "location"))
        if intent == IntentType.CREATE_EVENT:
            return all(data.get(field) for field in ("title", "event_date", "location"))
        return True

    def _build_menu_result(self, intro: str | None = None, *, language: str) -> BotRouteResult:
        if language == "en":
            lines = [
                intro or "Hi, I can help you with the community marketplace.",
                "You can ask me to:",
                "- publish an exchange offer",
                "- search exchange offers",
                "- publish an item for sale",
                "- browse listings",
                "- publish a community event",
                "- show a summary of active posts",
                "Examples:",
                "- I want to exchange 300 soles for pounds in Leeds city centre",
                "- I'm selling a microwave in Headingley for 25 pounds",
                "- There is a football match on Saturday at 6pm in Hyde Park",
            ]
        else:
            lines = [
                intro or "Hola, puedo ayudarte con el mercado comunitario.",
                "Puedes pedirme:",
                "- publicar una oferta de cambio",
                "- buscar ofertas de cambio",
                "- publicar un articulo a la venta",
                "- ver anuncios",
                "- publicar un evento comunitario",
                "- ver un resumen de las publicaciones activas",
                "Ejemplos:",
                "- Quiero cambiar 300 soles por libras en el centro de Leeds",
                "- Vendo un microondas en Headingley por 25 libras",
                "- Hay un partido de futbol el sabado a las 18:00 en Hyde Park",
            ]
        return BotRouteResult(reply_text="\n".join(lines), intent=IntentType.HELP_MENU)
