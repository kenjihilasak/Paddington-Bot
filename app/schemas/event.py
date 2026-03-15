"""Community event schemas."""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.db.models import RecordStatus


class CommunityEventCreate(BaseModel):
    """Community event creation schema."""

    user_id: int
    title: str = Field(min_length=2, max_length=255)
    description: str | None = None
    event_date: datetime
    location: str | None = Field(default=None, max_length=255)
    status: RecordStatus = RecordStatus.ACTIVE

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 2:
            raise ValueError("Title must be at least 2 characters long.")
        return normalized

    @field_validator("description", "location")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("event_date")
    @classmethod
    def normalize_event_date(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class CommunityEventRead(BaseModel):
    """Community event response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    title: str
    description: str | None
    event_date: datetime
    location: str | None
    status: RecordStatus
    created_at: datetime
