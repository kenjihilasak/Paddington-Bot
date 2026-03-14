"""Summary response schemas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class SummaryItem(BaseModel):
    """Single summary row."""

    id: int
    title: str
    location: str | None = None
    amount: Decimal | None = None
    currency: str | None = None
    secondary_currency: str | None = None
    event_date: datetime | None = None
    description: str | None = None


class SummarySection(BaseModel):
    """Summary section for one record type."""

    count: int
    items: list[SummaryItem]


class SummaryResponse(BaseModel):
    """Aggregated summary response."""

    generated_at: datetime
    exchange_offers: SummarySection
    listings: SummarySection
    events: SummarySection

