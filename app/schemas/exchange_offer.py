"""Exchange offer schemas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.db.models import RecordStatus


class ExchangeOfferCreate(BaseModel):
    """Exchange offer creation schema."""

    user_id: int
    offer_currency: str = Field(min_length=3, max_length=8)
    want_currency: str = Field(min_length=3, max_length=8)
    amount: Decimal = Field(gt=0)
    location: str | None = Field(default=None, max_length=255)
    notes: str | None = None
    status: RecordStatus = RecordStatus.ACTIVE
    expires_at: datetime | None = None


class ExchangeOfferRead(BaseModel):
    """Exchange offer response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    offer_currency: str
    want_currency: str
    amount: Decimal
    location: str | None
    notes: str | None
    status: RecordStatus
    created_at: datetime
    expires_at: datetime | None

