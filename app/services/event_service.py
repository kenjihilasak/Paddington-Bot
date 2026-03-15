"""Community event service."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CommunityEvent, RecordStatus
from app.db.repositories import CommunityEventRepository, UserRepository
from app.schemas.event import CommunityEventCreate
from app.services.exceptions import ResourceNotFoundError


class EventService:
    """Business logic for community events."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = CommunityEventRepository(session)
        self.user_repository = UserRepository(session)

    async def create_event(self, payload: CommunityEventCreate) -> CommunityEvent:
        """Create a new event."""

        user = await self.user_repository.get_by_id(payload.user_id)
        if user is None:
            raise ResourceNotFoundError("User not found.")

        event = CommunityEvent(
            user_id=payload.user_id,
            title=payload.title,
            description=payload.description,
            event_date=payload.event_date,
            location=payload.location,
            status=payload.status,
        )
        await self.repository.create(event)
        await self.session.commit()
        await self.session.refresh(event)
        return event

    async def list_events(
        self,
        *,
        location: str | None = None,
        status: RecordStatus | None = None,
        upcoming_only: bool = True,
        limit: int = 20,
        offset: int = 0,
    ) -> list[CommunityEvent]:
        """List community events."""

        return await self.repository.list(
            location=location,
            status=status,
            upcoming_only=upcoming_only,
            limit=limit,
            offset=offset,
        )
