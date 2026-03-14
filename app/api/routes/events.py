"""Community event routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_event_service
from app.db.models import RecordStatus
from app.schemas.event import CommunityEventCreate, CommunityEventRead
from app.services.event_service import EventService


router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("", response_model=list[CommunityEventRead])
async def list_events(
    location: str | None = Query(default=None),
    status_filter: RecordStatus | None = Query(default=None, alias="status"),
    upcoming_only: bool = Query(default=True),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    service: EventService = Depends(get_event_service),
) -> list[CommunityEventRead]:
    events = await service.list_events(
        location=location,
        status=status_filter,
        upcoming_only=upcoming_only,
        limit=limit,
        offset=offset,
    )
    return [CommunityEventRead.model_validate(item) for item in events]


@router.post("", response_model=CommunityEventRead, status_code=status.HTTP_201_CREATED)
async def create_event(
    payload: CommunityEventCreate,
    service: EventService = Depends(get_event_service),
) -> CommunityEventRead:
    event = await service.create_event(payload)
    return CommunityEventRead.model_validate(event)

