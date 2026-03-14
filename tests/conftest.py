"""Shared test fixtures."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api import deps
from app.db.base import Base
from app.db.models import User
from app.main import create_app


class FakeRedis:
    """Minimal async Redis replacement for tests."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        self._store[key] = value
        return True

    async def delete(self, key: str) -> int:
        existed = key in self._store
        self._store.pop(key, None)
        return 1 if existed else 0

    async def ping(self) -> bool:
        return True


@pytest.fixture
def fake_redis() -> FakeRedis:
    return FakeRedis()


@pytest.fixture
def session_maker(tmp_path: Path):
    database_path = tmp_path / "test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}", future=True)

    async def initialize() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    asyncio.run(initialize())
    maker = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    yield maker

    async def shutdown() -> None:
        await engine.dispose()

    asyncio.run(shutdown())


@pytest.fixture
def app(session_maker, fake_redis):
    app = create_app()

    async def override_get_db_session():
        async with session_maker() as session:
            yield session

    async def override_get_redis_client():
        return fake_redis

    async def override_get_llm_provider():
        return None

    app.dependency_overrides[deps.get_db_session] = override_get_db_session
    app.dependency_overrides[deps.get_redis_client] = override_get_redis_client
    app.dependency_overrides[deps.get_llm_provider] = override_get_llm_provider
    return app


@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def create_user(session_maker):
    def _create_user(*, wa_id: str = "447700900123", display_name: str = "Kenji") -> int:
        async def create() -> int:
            async with session_maker() as session:
                user = User(wa_id=wa_id, display_name=display_name)
                session.add(user)
                await session.commit()
                await session.refresh(user)
                return user.id

        return asyncio.run(create())

    return _create_user

