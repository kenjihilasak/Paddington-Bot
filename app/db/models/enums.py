"""Shared database enums."""

from __future__ import annotations

from enum import Enum


class MessageDirection(str, Enum):
    """Inbound or outbound message direction."""

    INBOUND = "inbound"
    OUTBOUND = "outbound"


class MessageType(str, Enum):
    """Supported message types."""

    TEXT = "text"
    UNSUPPORTED = "unsupported"


class RecordStatus(str, Enum):
    """Lifecycle status for stored business records."""

    ACTIVE = "active"
    RESOLVED = "resolved"
    CANCELLED = "cancelled"
    INACTIVE = "inactive"
    EXPIRED = "expired"
    ARCHIVED = "archived"


class ListingCategory(str, Enum):
    """Listing category values."""

    ITEM = "item"
    SERVICE = "service"
    WANTED = "wanted"
    OTHER = "other"


class ConversationFlow(str, Enum):
    """Conversation flow identifiers."""

    IDLE = "idle"
    EXCHANGE_CREATE = "exchange_create"
    EXCHANGE_SEARCH = "exchange_search"
    LISTING_CREATE = "listing_create"
    LISTING_SEARCH = "listing_search"
    EVENT_CREATE = "event_create"
    SUMMARY = "summary"

