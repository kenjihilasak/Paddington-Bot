"""Message repository."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Message, MessageDirection, MessageType


class MessageRepository:
    """Database operations for messages."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        user_id: int,
        direction: MessageDirection,
        message_type: MessageType,
        text: str | None,
        raw_payload: dict[str, Any] | None,
    ) -> Message:
        message = Message(
            user_id=user_id,
            direction=direction,
            message_type=message_type,
            text=text,
            raw_payload=raw_payload,
        )
        self.session.add(message)
        await self.session.flush()
        return message
