"""Shared test fixtures."""

from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api import deps
from app.db.base import Base
from app.db.models import User
from app.main import create_app
from app.services.webhook_task_coordinator import WebhookTaskCoordinator


class FakeRedis:
    """Minimal async Redis replacement for tests."""

    def __init__(self) -> None:
        self._store: dict[str, object] = {}

    async def get(self, key: str) -> str | None:
        value = self._store.get(key)
        return value if isinstance(value, str) else None

    async def set(self, key: str, value: str, ex: int | None = None, nx: bool = False) -> bool:
        if nx and key in self._store:
            return False
        self._store[key] = value
        return True

    async def delete(self, *keys: str) -> int:
        deleted = 0
        for key in keys:
            if key in self._store:
                deleted += 1
                self._store.pop(key, None)
        return deleted

    async def rpush(self, key: str, *values: str) -> int:
        items = self._store.setdefault(key, [])
        if not isinstance(items, list):
            msg = f"Key {key} is not a list."
            raise TypeError(msg)
        items.extend(values)
        return len(items)

    async def lpop(self, key: str) -> str | None:
        items = self._store.get(key)
        if not isinstance(items, list) or not items:
            return None
        value = items.pop(0)
        if not items:
            self._store.pop(key, None)
        return value

    async def expire(self, key: str, seconds: int) -> bool:
        return key in self._store

    async def llen(self, key: str) -> int:
        items = self._store.get(key)
        return len(items) if isinstance(items, list) else 0

    async def eval(self, script: str, numkeys: int, *keys_and_args: str) -> int:
        keys = keys_and_args[:numkeys]
        args = keys_and_args[numkeys:]

        if "LLEN" in script:
            lock_key, queue_key = keys
            expected_owner = args[0]
            if self._store.get(lock_key) != expected_owner:
                return -1
            if await self.llen(queue_key) > 0:
                return 0
            await self.delete(lock_key)
            return 1

        lock_key = keys[0]
        expected_owner = args[0]
        if self._store.get(lock_key) != expected_owner:
            return 0
        await self.delete(lock_key)
        return 1

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
    shared_http_client = httpx.AsyncClient()
    app.state.redis = fake_redis
    app.state.http_client = shared_http_client
    app.state.session_maker = session_maker
    app.state.webhook_task_coordinator = WebhookTaskCoordinator(
        session_factory=session_maker,
        settings=deps.get_app_settings(),
        redis_client=fake_redis,
        http_client=shared_http_client,
    )

    async def override_get_db_session():
        async with session_maker() as session:
            yield session

    async def override_get_redis_client():
        return fake_redis

    async def override_get_llm_provider():
        return None

    async def override_get_intent_classifier():
        return None

    async def override_get_http_client():
        return shared_http_client

    app.dependency_overrides[deps.get_db_session] = override_get_db_session
    app.dependency_overrides[deps.get_redis_client] = override_get_redis_client
    app.dependency_overrides[deps.get_http_client] = override_get_http_client
    app.dependency_overrides[deps.get_llm_provider] = override_get_llm_provider
    app.dependency_overrides[deps.get_intent_classifier] = override_get_intent_classifier
    yield app
    assert app.state.webhook_task_coordinator.wait_until_idle(5.0)
    asyncio.run(shared_http_client.aclose())


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

