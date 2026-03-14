"""Community event schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.db.models import RecordStatus


class CommunityEventCreate(BaseModel):
    """Community event creation schema."""

    user_id: int
    title: str = Field(min_length=2, max_length=255)
    description: str | None = None
    event_date: datetime
    location: str | None = Field(default=None, max_length=255)
    status: RecordStatus = RecordStatus.ACTIVE


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

