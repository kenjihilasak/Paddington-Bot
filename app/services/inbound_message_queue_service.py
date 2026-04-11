"""Redis-backed inbound message coordination for dedupe, queueing, and locks."""

from __future__ import annotations

import uuid

from redis.asyncio import Redis

from app.core.config import Settings
from app.schemas.bot import NormalizedInboundMessage


_RELEASE_LOCK_IF_EMPTY_SCRIPT = """
local lock_key = KEYS[1]
local queue_key = KEYS[2]
local expected_owner = ARGV[1]

if redis.call("GET", lock_key) ~= expected_owner then
    return -1
end

if redis.call("LLEN", queue_key) > 0 then
    return 0
end

redis.call("DEL", lock_key)
return 1
"""

_RELEASE_LOCK_IF_OWNER_SCRIPT = """
local lock_key = KEYS[1]
local expected_owner = ARGV[1]

if redis.call("GET", lock_key) ~= expected_owner then
    return 0
end

redis.call("DEL", lock_key)
return 1
"""


class InboundMessageQueueService:
    """Coordinate inbound webhook processing across concurrent workers."""

    def __init__(self, redis_client: Redis, settings: Settings) -> None:
        self.redis_client = redis_client
        self.settings = settings

    @staticmethod
    def build_dedupe_key(message_id: str) -> str:
        return f"inbound-message:seen:{message_id}"

    @staticmethod
    def build_lock_key(wa_id: str) -> str:
        return f"inbound-message:lock:{wa_id}"

    @staticmethod
    def build_queue_key(wa_id: str) -> str:
        return f"inbound-message:queue:{wa_id}"

    async def enqueue_message(self, inbound: NormalizedInboundMessage) -> bool:
        """Store a normalized inbound message unless it has already been seen."""

        if inbound.message_id:
            was_marked = await self.redis_client.set(
                self.build_dedupe_key(inbound.message_id),
                "1",
                ex=self.settings.inbound_message_dedupe_ttl_seconds,
                nx=True,
            )
            if not was_marked:
                return False

        queue_key = self.build_queue_key(inbound.wa_id)
        await self.redis_client.rpush(queue_key, inbound.model_dump_json())
        await self.redis_client.expire(queue_key, self.settings.inbound_message_queue_ttl_seconds)
        return True

    async def try_acquire_user_lock(self, wa_id: str) -> str | None:
        """Claim exclusive processing for a WhatsApp user if available."""

        owner_token = uuid.uuid4().hex
        acquired = await self.redis_client.set(
            self.build_lock_key(wa_id),
            owner_token,
            ex=self.settings.inbound_message_lock_ttl_seconds,
            nx=True,
        )
        if not acquired:
            return None
        return owner_token

    async def pop_next_message(self, wa_id: str) -> NormalizedInboundMessage | None:
        """Pop the next queued inbound message for a WhatsApp user."""

        raw_value = await self.redis_client.lpop(self.build_queue_key(wa_id))
        if raw_value is None:
            return None
        if isinstance(raw_value, bytes):
            raw_value = raw_value.decode("utf-8")
        return NormalizedInboundMessage.model_validate_json(raw_value)

    async def has_queued_messages(self, wa_id: str) -> bool:
        """Return whether a WhatsApp user still has queued inbound messages."""

        return int(await self.redis_client.llen(self.build_queue_key(wa_id))) > 0

    async def release_user_lock_if_queue_empty(self, wa_id: str, owner_token: str) -> bool:
        """Release the user lock only when the queue is empty at that instant."""

        result = await self.redis_client.eval(
            _RELEASE_LOCK_IF_EMPTY_SCRIPT,
            2,
            self.build_lock_key(wa_id),
            self.build_queue_key(wa_id),
            owner_token,
        )
        return int(result) == 1

    async def release_user_lock(self, wa_id: str, owner_token: str) -> bool:
        """Best-effort owner-checked lock release for error paths."""

        result = await self.redis_client.eval(
            _RELEASE_LOCK_IF_OWNER_SCRIPT,
            1,
            self.build_lock_key(wa_id),
            owner_token,
        )
        return int(result) == 1
