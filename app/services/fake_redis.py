"""In-memory Redis replacement for local development and tests."""

from __future__ import annotations


class FakeRedis:
    """Provide the subset of async Redis operations used by the app."""

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

    async def aclose(self) -> None:
        self._store.clear()
