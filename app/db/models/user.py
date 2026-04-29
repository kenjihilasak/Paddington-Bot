"""User model."""

from __future__ import annotations

from typing import Any
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym

from app.db.base import Base


class User(Base):
    """WhatsApp user known to the system."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    wa_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    wa_profile_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    profile_photo_source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone_country_prefix: Mapped[str | None] = mapped_column(String(8), nullable=True)
    country_code: Mapped[str | None] = mapped_column(String(8), nullable=True)
    profile_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    display_name = synonym("wa_profile_name")

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

    @property
    def preferred_name(self) -> str | None:
        return self.name or self.wa_profile_name

