"""Exchange offer model."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.enums import RecordStatus


class ExchangeOffer(Base):
    """Currency exchange offer posted by a user."""

    __tablename__ = "exchange_offers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    offer_currency: Mapped[str] = mapped_column(String(8), index=True)
    want_currency: Mapped[str] = mapped_column(String(8), index=True)
    want_currencies: Mapped[list[str]] = mapped_column(JSON, default=list)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    location: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[RecordStatus] = mapped_column(
        Enum(RecordStatus), default=RecordStatus.ACTIVE, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="exchange_offers")

