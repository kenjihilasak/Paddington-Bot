"""Conversation state model."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.enums import ConversationFlow


class ConversationState(Base):
    """Durable snapshot of a user's current bot flow."""

    __tablename__ = "conversation_states"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    current_flow: Mapped[ConversationFlow] = mapped_column(
        Enum(ConversationFlow), default=ConversationFlow.IDLE, index=True
    )
    current_step: Mapped[str | None] = mapped_column(String(100), nullable=True)
    draft_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    user = relationship("User", back_populates="conversation_state")
