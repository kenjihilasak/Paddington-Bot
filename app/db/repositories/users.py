"""User repository."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User


class UserRepository:
    """Database operations for users."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, user_id: int) -> User | None:
        return await self.session.get(User, user_id)

    async def get_by_wa_id(self, wa_id: str) -> User | None:
        result = await self.session.execute(select(User).where(User.wa_id == wa_id))
        return result.scalar_one_or_none()

    async def upsert_whatsapp_user(self, wa_id: str, wa_profile_name: str | None = None) -> User:
        user = await self.get_by_wa_id(wa_id)
        if user is None:
            user = User(wa_id=wa_id, wa_profile_name=wa_profile_name)
            self.session.add(user)
        elif wa_profile_name:
            user.wa_profile_name = wa_profile_name
        await self.session.flush()
        return user

