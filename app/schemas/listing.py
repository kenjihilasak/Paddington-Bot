"""Listing schemas."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.db.models import ListingCategory, RecordStatus


class ListingCreate(BaseModel):
    """Listing creation schema."""

    user_id: int
    category: ListingCategory = ListingCategory.ITEM
    title: str = Field(min_length=2, max_length=255)
    description: str | None = None
    price: Decimal = Field(gt=0)
    currency: str = Field(default="GBP", min_length=3, max_length=8)
    location: str | None = Field(default=None, max_length=255)
    status: RecordStatus = RecordStatus.ACTIVE
    expires_at: datetime | None = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 2:
            raise ValueError("Title must be at least 2 characters long.")
        return normalized

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not re.fullmatch(r"[A-Z]{3,8}", normalized):
            raise ValueError("Currency codes must contain 3 to 8 letters.")
        return normalized

    @field_validator("description", "location")
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


class ListingRead(BaseModel):
    """Listing response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    category: ListingCategory
    title: str
    description: str | None
    price: Decimal
    currency: str
    location: str | None
    status: RecordStatus
    created_at: datetime
    expires_at: datetime | None
