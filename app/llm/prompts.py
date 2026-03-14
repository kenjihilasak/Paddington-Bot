"""Prompt builders for the OpenAI-compatible provider."""

from __future__ import annotations

from app.schemas.bot import IntentType


def build_intent_system_prompt() -> str:
    """Return the system prompt for intent classification."""

    return (
        "You are classifying WhatsApp user messages for a community marketplace bot in Leeds. "
        "Return strict JSON with keys intent and confidence. Supported intents are: "
        "help_menu, summary, create_exchange_offer, search_exchange_offers, "
        "create_listing, search_listings, create_event, unknown."
    )


def build_extraction_system_prompt(intent: IntentType | None) -> str:
    """Return the system prompt for structured extraction."""

    intent_name = intent.value if intent else "unknown"
    return (
        "You extract structured data from WhatsApp marketplace messages. "
        "Return strict JSON with keys intent, confidence, and data. "
        f"The preferred intent is {intent_name}. "
        "Use only the data the user explicitly or strongly implies. "
        "Do not invent missing values."
    )

