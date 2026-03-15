"""Inbound message routing and bot flow orchestration."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from zoneinfo import ZoneInfo

import dateparser

from app.core.config import Settings
from app.db.models import ConversationFlow, ListingCategory, User
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

CURRENCY_ALIASES = {
    "pound": "GBP",
    "pounds": "GBP",
    "gbp": "GBP",
    "sterling": "GBP",
    "euro": "EUR",
    "euros": "EUR",
    "eur": "EUR",
    "sol": "PEN",
    "soles": "PEN",
    "pen": "PEN",
    "dollar": "USD",
    "dollars": "USD",
    "usd": "USD",
}
CURRENCY_WORD_PATTERN = re.compile(
    r"\b(pounds?|gbp|sterling|euros?|eur|soles?|pen|dollars?|usd)\b", re.IGNORECASE
)
AMOUNT_WITH_CURRENCY_PATTERN = re.compile(
    r"(?P<amount>\d+(?:\.\d+)?)\s*(?P<currency>pounds?|gbp|sterling|euros?|eur|soles?|pen|dollars?|usd)",
    re.IGNORECASE,
)
PRICE_PATTERN = re.compile(
    r"\b(?:for|price(?:d)? at)\s*(?P<amount>\d+(?:\.\d+)?)\s*(?P<currency>pounds?|gbp|sterling|euros?|eur|soles?|pen|dollars?|usd)?",
    re.IGNORECASE,
)
HELP_KEYWORDS = ("help", "menu", "options")
SUMMARY_KEYWORDS = ("summary", "recap", "overview")
SEARCH_MARKERS = ("show me", "find", "search", "do you have", "anyone", "looking for")
LISTING_CREATE_MARKERS = ("i'm selling", "i am selling", "selling", "for sale")
LISTING_SEARCH_MARKERS = ("show me listings", "find listings", "search listings", "browse listings")
EVENT_KEYWORDS = ("event", "match", "meetup", "meeting", "workshop", "football")
DAY_KEYWORDS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
SELL_COMMANDS = ("sell", "selling")


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
        llm_provider: LLMProvider | None = None,
    ) -> None:
        self.settings = settings
        self.conversation_state_service = conversation_state_service
        self.exchange_service = exchange_service
        self.listing_service = listing_service
        self.event_service = event_service
        self.summary_service = summary_service
        self.llm_provider = llm_provider

    async def route_message(self, *, user: User, message_text: str) -> BotRouteResult:
        """Route a single inbound message."""

        normalized = self._normalize_text(message_text)
        if normalized in {"cancel", "stop", "reset"}:
            await self.conversation_state_service.clear_state(user.id)
            return BotRouteResult(
                reply_text="Okay, I cleared your current draft. Send a new message whenever you are ready.",
                intent=IntentType.HELP_MENU,
            )

        if any(keyword in normalized for keyword in HELP_KEYWORDS):
            return self._build_menu_result()

        state = await self.conversation_state_service.get_state(user.id)
        if state and state.current_flow != ConversationFlow.IDLE:
            return await self._continue_existing_flow(user, message_text, state.draft_data, state.current_flow)

        intent_result = await self._classify_intent(message_text)
        if intent_result.intent == IntentType.HELP_MENU:
            return self._build_menu_result()
        if intent_result.intent == IntentType.SUMMARY:
            return BotRouteResult(
                reply_text=await self.summary_service.render_compact_text(),
                intent=IntentType.SUMMARY,
            )
        if intent_result.intent == IntentType.CREATE_EXCHANGE_OFFER:
            return await self._handle_exchange_create(user, message_text, {})
        if intent_result.intent == IntentType.SEARCH_EXCHANGE_OFFERS:
            return await self._handle_exchange_search(user, message_text, {})
        if intent_result.intent == IntentType.CREATE_LISTING:
            return await self._handle_listing_create(user, message_text, {})
        if intent_result.intent == IntentType.SEARCH_LISTINGS:
            return await self._handle_listing_search(message_text)
        if intent_result.intent == IntentType.CREATE_EVENT:
            return await self._handle_event_create(user, message_text, {})

        return self._build_menu_result(
            "I did not fully understand that, but I can still help. Here are the main things I can do:"
        )

    async def _continue_existing_flow(
        self,
        user: User,
        message_text: str,
        draft_data: dict[str, Any],
        flow: ConversationFlow,
    ) -> BotRouteResult:
        if flow == ConversationFlow.EXCHANGE_CREATE:
            return await self._handle_exchange_create(user, message_text, draft_data)
        if flow == ConversationFlow.EXCHANGE_SEARCH:
            return await self._handle_exchange_search(user, message_text, draft_data)
        if flow == ConversationFlow.LISTING_CREATE:
            return await self._handle_listing_create(user, message_text, draft_data)
        if flow == ConversationFlow.EVENT_CREATE:
            return await self._handle_event_create(user, message_text, draft_data)
        return self._build_menu_result()

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
        if "exchange" in normalized or "changing" in normalized or currency_count >= 2:
            if any(marker in normalized for marker in SEARCH_MARKERS):
                return IntentResult(intent=IntentType.SEARCH_EXCHANGE_OFFERS, confidence=0.87)
            return IntentResult(intent=IntentType.CREATE_EXCHANGE_OFFER, confidence=0.84)
        if self._looks_like_event(message_text):
            return IntentResult(intent=IntentType.CREATE_EVENT, confidence=0.82)

        if self.llm_provider:
            try:
                llm_result = await self.llm_provider.classify_intent(message_text, context={})
                return llm_result
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.warning("LLM intent classification failed: %s", exc)

        return IntentResult(intent=IntentType.UNKNOWN, confidence=0.0)

    async def _handle_exchange_create(
        self, user: User, message_text: str, existing_draft: dict[str, Any]
    ) -> BotRouteResult:
        data = await self._extract_data(IntentType.CREATE_EXCHANGE_OFFER, message_text, existing_draft)
        missing_fields = [field for field in ("offer_currency", "want_currency", "amount", "location") if not data.get(field)]
        if missing_fields:
            next_field = missing_fields[0]
            await self.conversation_state_service.save_state(
                user_id=user.id,
                current_flow=ConversationFlow.EXCHANGE_CREATE,
                current_step=next_field,
                draft_data=data,
                last_user_message=message_text,
            )
            return BotRouteResult(
                reply_text=self._follow_up_question(IntentType.CREATE_EXCHANGE_OFFER, next_field),
                intent=IntentType.CREATE_EXCHANGE_OFFER,
            )

        payload = ExchangeOfferCreate(
            user_id=user.id,
            offer_currency=data["offer_currency"],
            want_currency=data["want_currency"],
            amount=data["amount"],
            location=data.get("location"),
            notes=data.get("notes"),
        )
        offer = await self.exchange_service.create_offer(payload)
        await self.conversation_state_service.clear_state(user.id)
        return BotRouteResult(
            reply_text=(
                f"I have posted your exchange offer: {offer.amount} {offer.offer_currency} to "
                f"{offer.want_currency}" + (f" in {offer.location}." if offer.location else ".")
            ),
            intent=IntentType.CREATE_EXCHANGE_OFFER,
            metadata={"exchange_offer_id": offer.id},
        )

    async def _handle_exchange_search(
        self, user: User, message_text: str, existing_draft: dict[str, Any]
    ) -> BotRouteResult:
        data = await self._extract_data(IntentType.SEARCH_EXCHANGE_OFFERS, message_text, existing_draft)
        if not data.get("offer_currency") and not data.get("want_currency"):
            await self.conversation_state_service.save_state(
                user_id=user.id,
                current_flow=ConversationFlow.EXCHANGE_SEARCH,
                current_step="currency_pair",
                draft_data=data,
                last_user_message=message_text,
            )
            return BotRouteResult(
                reply_text="Which currencies are you looking for? For example: pounds to euros.",
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
                reply_text="I could not find any active exchange offers matching that request right now.",
                intent=IntentType.SEARCH_EXCHANGE_OFFERS,
            )

        lines = ["Here are the closest exchange offers:"]
        for item in offers[:5]:
            line = f"- {item.amount} {item.offer_currency} to {item.want_currency}"
            if item.location:
                line += f" in {item.location}"
            lines.append(line)
        return BotRouteResult(
            reply_text="\n".join(lines),
            intent=IntentType.SEARCH_EXCHANGE_OFFERS,
        )

    async def _handle_listing_create(
        self, user: User, message_text: str, existing_draft: dict[str, Any]
    ) -> BotRouteResult:
        data = await self._extract_data(IntentType.CREATE_LISTING, message_text, existing_draft)
        missing_fields = [field for field in ("title", "price", "location") if not data.get(field)]
        if missing_fields:
            next_field = missing_fields[0]
            await self.conversation_state_service.save_state(
                user_id=user.id,
                current_flow=ConversationFlow.LISTING_CREATE,
                current_step=next_field,
                draft_data=data,
                last_user_message=message_text,
            )
            return BotRouteResult(
                reply_text=self._follow_up_question(IntentType.CREATE_LISTING, next_field),
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
                f"I have posted your listing for {listing.title} at {listing.price} {listing.currency}"
                + (f" in {listing.location}." if listing.location else ".")
            ),
            intent=IntentType.CREATE_LISTING,
            metadata={"listing_id": listing.id},
        )

    async def _handle_listing_search(self, message_text: str) -> BotRouteResult:
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
                reply_text="I could not find any active listings matching that search.",
                intent=IntentType.SEARCH_LISTINGS,
            )

        lines = ["Here are the latest listings:"]
        for item in listings[:5]:
            line = f"- {item.title} for {item.price} {item.currency}"
            if item.location:
                line += f" in {item.location}"
            lines.append(line)
        return BotRouteResult(reply_text="\n".join(lines), intent=IntentType.SEARCH_LISTINGS)

    async def _handle_event_create(
        self, user: User, message_text: str, existing_draft: dict[str, Any]
    ) -> BotRouteResult:
        data = await self._extract_data(IntentType.CREATE_EVENT, message_text, existing_draft)
        missing_fields = [field for field in ("title", "event_date", "location") if not data.get(field)]
        if missing_fields:
            next_field = missing_fields[0]
            await self.conversation_state_service.save_state(
                user_id=user.id,
                current_flow=ConversationFlow.EVENT_CREATE,
                current_step=next_field,
                draft_data=data,
                last_user_message=message_text,
            )
            return BotRouteResult(
                reply_text=self._follow_up_question(IntentType.CREATE_EVENT, next_field),
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
                f"I have posted your event: {event.title}"
                f" on {event.event_date.strftime('%a %d %b %H:%M')}"
                + (f" in {event.location}." if event.location else ".")
            ),
            intent=IntentType.CREATE_EVENT,
            metadata={"event_id": event.id},
        )

    async def _extract_data(
        self, intent: IntentType, message_text: str, existing_draft: dict[str, Any]
    ) -> dict[str, Any]:
        rule_data = self._rule_extract(intent, message_text)
        merged = {**existing_draft, **{key: value for key, value in rule_data.items() if value is not None}}

        should_try_llm = self.llm_provider is not None and not self._is_data_sufficient(intent, merged)
        if should_try_llm:
            try:
                llm_result = await self.llm_provider.extract_structured_data(
                    message_text,
                    context={"draft_data": existing_draft},
                    intent=intent,
                )
                merged = {
                    **llm_result.data,
                    **{key: value for key, value in merged.items() if value is not None},
                }
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.warning("LLM extraction failed for %s: %s", intent.value, exc)
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
        if amount_match:
            data["amount"] = self._safe_decimal(amount_match.group("amount"))
            data["offer_currency"] = self._normalize_currency(amount_match.group("currency"))

        if "offer_currency" not in data and currencies:
            data["offer_currency"] = currencies[0]
        if len(currencies) >= 2:
            if currencies[0] == data.get("offer_currency") and len(currencies) >= 2:
                data["want_currency"] = currencies[1]
            elif "offer_currency" not in data:
                data["offer_currency"] = currencies[0]
                data["want_currency"] = currencies[1]

        data["location"] = self._extract_location(message_text)
        return {key: value for key, value in data.items() if value is not None}

    def _extract_listing_data(self, message_text: str) -> dict[str, Any]:
        data: dict[str, Any] = {"description": message_text, "currency": "GBP"}
        title_match = re.search(
            r"(?:i am selling|i'm selling|selling|for sale)\s+(?:an?\s+|the\s+)?(?P<title>.+?)(?:\s+in\s+|\s+for\s+\d|$)",
            message_text,
            re.IGNORECASE,
        )
        if title_match:
            data["title"] = title_match.group("title").strip(" .,!?")

        price_match = PRICE_PATTERN.search(message_text)
        if price_match:
            data["price"] = self._safe_decimal(price_match.group("amount"))
            currency_word = price_match.group("currency")
            if currency_word:
                data["currency"] = self._normalize_currency(currency_word)

        data["location"] = self._extract_location(message_text)
        return {key: value for key, value in data.items() if value is not None}

    def _extract_listing_search_data(self, message_text: str) -> dict[str, Any]:
        location = self._extract_location(message_text)
        cleaned = re.sub(r"\b(show me|find|search|browse|listings?|items?)\b", "", message_text, flags=re.IGNORECASE)
        if location:
            cleaned = re.sub(rf"\bin\s+{re.escape(location)}\b", "", cleaned, flags=re.IGNORECASE)
        search_text = cleaned.strip(" .!?")
        data: dict[str, Any] = {}
        if location:
            data["location"] = location
        if search_text and len(search_text) > 2:
            data["search_text"] = search_text
        return data

    def _extract_event_data(self, message_text: str) -> dict[str, Any]:
        cleaned = re.sub(r"^(there is|there's|there will be|event:?|community event:?|join us for)\s+", "", message_text, flags=re.IGNORECASE).strip()
        title = re.split(r"\b(?:on|at|in)\b", cleaned, maxsplit=1, flags=re.IGNORECASE)[0].strip(" .,!?")
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

    @staticmethod
    def _normalize_currency(value: str) -> str | None:
        normalized = CURRENCY_ALIASES.get(value.strip().lower())
        return normalized

    @staticmethod
    def _normalize_text(message_text: str) -> str:
        return " ".join(message_text.lower().strip().split())

    def _extract_location(self, message_text: str) -> str | None:
        in_match = re.search(r"\bin\s+([A-Za-z][A-Za-z\s'-]{1,80})", message_text, re.IGNORECASE)
        if in_match:
            return in_match.group(1).strip(" .,!?")
        at_match = re.search(r"\bat\s+([A-Za-z][A-Za-z\s'-]{1,80})", message_text, re.IGNORECASE)
        if at_match and not any(character.isdigit() for character in at_match.group(1)):
            return at_match.group(1).strip(" .,!?")
        return None

    def _parse_event_date(self, message_text: str) -> datetime | None:
        timezone_name = self.settings.business_timezone
        candidate_fragments: list[str] = []
        fragment_match = re.search(
            r"\b(?:on|at)\s+(.+?)(?:\s+in\s+[A-Za-z][A-Za-z\s'-]{1,80})?$",
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

    def _looks_like_event(self, message_text: str) -> bool:
        normalized = self._normalize_text(message_text)
        if any(keyword in normalized for keyword in EVENT_KEYWORDS):
            return True
        return any(day in normalized for day in DAY_KEYWORDS) and self._parse_event_date(message_text) is not None

    def _follow_up_question(self, intent: IntentType, field_name: str) -> str:
        prompts = {
            IntentType.CREATE_EXCHANGE_OFFER: {
                "offer_currency": "Which currency do you want to offer?",
                "want_currency": "Which currency do you want in return?",
                "amount": "How much money do you want to exchange?",
                "location": "Where in Leeds would you like to meet?",
            },
            IntentType.CREATE_LISTING: {
                "title": "What item are you selling?",
                "price": "What price would you like to post?",
                "location": "Where is the item available?",
            },
            IntentType.CREATE_EVENT: {
                "title": "What is the event title?",
                "event_date": "When is the event happening?",
                "location": "Where is the event taking place?",
            },
        }
        return prompts[intent][field_name]

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

    def _build_menu_result(self, intro: str | None = None) -> BotRouteResult:
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
        return BotRouteResult(reply_text="\n".join(lines), intent=IntentType.HELP_MENU)
