"""User model."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class User(Base):
    """WhatsApp user known to the system."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    wa_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    messages = relationship("Message", back_populates="user", cascade="all, delete-orphan")
    conversation_state = relationship(
        "ConversationState", back_populates="user", cascade="all, delete-orphan", uselist=False
    )
    exchange_offers = relationship(
        "ExchangeOffer", back_populates="user", cascade="all, delete-orphan"
    )
    listings = relationship("Listing", back_populates="user", cascade="all, delete-orphan")
    community_events = relationship(
        "CommunityEvent", back_populates="user", cascade="all, delete-orphan"
    )

