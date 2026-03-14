"""Listing schemas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

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
