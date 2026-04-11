"""Conversation state management backed by Redis and PostgreSQL."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.models import ConversationFlow
from app.db.repositories import ConversationStateRepository
from app.schemas.bot import ConversationStatePayload


class ConversationStateService:
    """Store active conversation state in Redis and mirror it into PostgreSQL."""

    def __init__(self, redis_client: Redis, session: AsyncSession, settings: Settings) -> None:
        self.redis_client = redis_client
        self.session = session
        self.settings = settings
        self.repository = ConversationStateRepository(session)

    @staticmethod
    def build_key(user_id: int) -> str:
        """Build the Redis key for a user conversation state."""

        return f"conversation-state:{user_id}"

    async def get_state(self, user_id: int) -> ConversationStatePayload | None:
        """Return the current state for the user if one exists."""

        raw_value = await self.redis_client.get(self.build_key(user_id))
        if raw_value:
            if isinstance(raw_value, bytes):
                raw_value = raw_value.decode("utf-8")
            return ConversationStatePayload.model_validate_json(raw_value)

        snapshot = await self.repository.get_by_user_id(user_id)
        if snapshot is None or snapshot.current_flow == ConversationFlow.IDLE:
            return None

        return ConversationStatePayload(
            current_flow=snapshot.current_flow,
            current_step=snapshot.current_step,
            draft_data=snapshot.draft_data,
            updated_at=snapshot.updated_at,
        )

    async def save_state(
        self,
        *,
        user_id: int,
        current_flow: ConversationFlow,
        current_step: str | None,
        draft_data: dict[str, Any],
        last_user_message: str | None,
    ) -> ConversationStatePayload:
        """Persist the current state in Redis and mirror it into PostgreSQL."""

        serializable_draft_data = self._make_json_safe(draft_data)
        payload = ConversationStatePayload(
            current_flow=current_flow,
            current_step=current_step,
            draft_data=serializable_draft_data,
            last_user_message=last_user_message,
            updated_at=datetime.now(timezone.utc),
        )
        await self.redis_client.set(
            self.build_key(user_id),
            payload.model_dump_json(),
            ex=self.settings.conversation_state_ttl_seconds,
        )
        await self.repository.upsert(
            user_id=user_id,
            current_flow=current_flow,
            current_step=current_step,
            draft_data=serializable_draft_data,
        )
        await self.session.commit()
        return payload

    async def clear_state(self, user_id: int) -> None:
        """Clear active state for the user in both Redis and PostgreSQL."""

        await self.redis_client.delete(self.build_key(user_id))
        await self.repository.clear(user_id)
        await self.session.commit()

    def _make_json_safe(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {key: self._make_json_safe(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._make_json_safe(item) for item in value]
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, datetime):
            if value.tzinfo is None or value.utcoffset() is None:
                value = value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc).isoformat()
        return value

