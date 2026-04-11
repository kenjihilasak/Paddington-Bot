"""Exchange offer schemas."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.db.models import RecordStatus


class ExchangeOfferCreate(BaseModel):
    """Exchange offer creation schema."""

    user_id: int
    offer_currency: str = Field(min_length=3, max_length=8)
    want_currency: str | None = Field(default=None, min_length=3, max_length=8)
    want_currencies: list[str] = Field(default_factory=list)
    amount: Decimal = Field(gt=0)
    location: str | None = Field(default=None, max_length=255)
    notes: str | None = None
    status: RecordStatus = RecordStatus.ACTIVE
    expires_at: datetime | None = None

    @field_validator("offer_currency", "want_currency")
    @classmethod
    def validate_currency(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().upper()
        if not re.fullmatch(r"[A-Z]{3,8}", normalized):
            raise ValueError("Currency codes must contain 3 to 8 letters.")
        return normalized

    @field_validator("want_currencies")
    @classmethod
    def validate_currency_list(cls, values: list[str]) -> list[str]:
        normalized_values: list[str] = []
        for value in values:
            normalized = cls.validate_currency(value)
            if normalized and normalized not in normalized_values:
                normalized_values.append(normalized)
        return normalized_values

    @field_validator("location", "notes")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("expires_at")
    @classmethod
    def normalize_expires_at(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def populate_want_currency_preferences(self) -> "ExchangeOfferCreate":
        values = list(self.want_currencies)
        if self.want_currency and self.want_currency not in values:
            values.insert(0, self.want_currency)
        if not values:
            raise ValueError("At least one target currency is required.")

        self.want_currencies = values
        self.want_currency = values[0]
        return self


class ExchangeOfferRead(BaseModel):
    """Exchange offer response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    offer_currency: str
    want_currency: str
    want_currencies: list[str]
    amount: Decimal
    location: str | None
    notes: str | None
    status: RecordStatus
    created_at: datetime
    expires_at: datetime | None
