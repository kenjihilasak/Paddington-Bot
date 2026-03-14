"""Conversation state repository."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ConversationFlow, ConversationState


class ConversationStateRepository:
    """Database operations for conversation state snapshots."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_user_id(self, user_id: int) -> ConversationState | None:
        result = await self.session.execute(
            select(ConversationState).where(ConversationState.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def upsert(
        self,
        *,
        user_id: int,
        current_flow: ConversationFlow,
        current_step: str | None,
        draft_data: dict[str, Any],
    ) -> ConversationState:
        state = await self.get_by_user_id(user_id)
        if state is None:
            state = ConversationState(
                user_id=user_id,
                current_flow=current_flow,
                current_step=current_step,
                draft_data=draft_data,
            )
            self.session.add(state)
        else:
            state.current_flow = current_flow
            state.current_step = current_step
            state.draft_data = draft_data
            state.updated_at = datetime.now(timezone.utc)
        await self.session.flush()
        return state

    async def clear(self, user_id: int) -> None:
        state = await self.get_by_user_id(user_id)
        if state is None:
            return
        state.current_flow = ConversationFlow.IDLE
        state.current_step = None
        state.draft_data = {}
        state.updated_at = datetime.now(timezone.utc)
        await self.session.flush()

