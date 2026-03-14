"""Schemas used by the message router and LLM provider."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from app.db.models import ConversationFlow


class IntentType(str, Enum):
    """Bot intent classification values."""

    HELP_MENU = "help_menu"
    SUMMARY = "summary"
    CREATE_EXCHANGE_OFFER = "create_exchange_offer"
    SEARCH_EXCHANGE_OFFERS = "search_exchange_offers"
    CREATE_LISTING = "create_listing"
    SEARCH_LISTINGS = "search_listings"
    CREATE_EVENT = "create_event"
    UNKNOWN = "unknown"


class IntentResult(BaseModel):
    """Intent classification result."""

    intent: IntentType
    confidence: float = 0.0
    source: str = "rule"


class ExtractionResult(BaseModel):
    """Structured extraction payload from rule-based or LLM parsing."""

    intent: IntentType
    confidence: float = 0.0
    data: dict[str, Any] = Field(default_factory=dict)
    source: str = "rule"


class NormalizedInboundMessage(BaseModel):
    """Normalized WhatsApp inbound text message."""

    wa_id: str
    display_name: str | None = None
    text: str
    timestamp: datetime
    raw_payload: dict[str, Any]
    message_id: str | None = None
    message_type: str = "text"


class BotRouteResult(BaseModel):
    """Message router output."""

    reply_text: str
    intent: IntentType
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConversationStatePayload(BaseModel):
    """Conversation state stored in Redis."""

    current_flow: ConversationFlow = ConversationFlow.IDLE
    current_step: str | None = None
    draft_data: dict[str, Any] = Field(default_factory=dict)
    last_user_message: str | None = None
    updated_at: datetime

