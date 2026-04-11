"""Webhook endpoint tests."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import func, select

from app.schemas.bot import BotRouteResult, IntentType, NormalizedInboundMessage
from app.core.config import get_settings
from app.db.models import Listing, Message, MessageDirection, User
from app.services.webhook_service import WebhookService


class StaticQueueService:
    """Minimal queue stub for exercising drain edge cases."""

    def __init__(self, inbound: NormalizedInboundMessage) -> None:
        self.inbound = inbound
        self._popped = False
        self._release_calls = 0

    async def try_acquire_user_lock(self, wa_id: str) -> str | None:
        return "owner-token"

    async def pop_next_message(self, wa_id: str) -> NormalizedInboundMessage | None:
        if self._popped:
            return None
        self._popped = True
        return self.inbound

    async def has_queued_messages(self, wa_id: str) -> bool:
        return False

    async def release_user_lock_if_queue_empty(self, wa_id: str, owner_token: str) -> bool:
        self._release_calls += 1
        return False

    async def release_user_lock(self, wa_id: str, owner_token: str) -> bool:
        return False


class StaticRouter:
    async def route_message(self, *, user: User, message_text: str) -> BotRouteResult:
        return BotRouteResult(
            reply_text=f"processed: {message_text}",
            intent=IntentType.CREATE_EXCHANGE_OFFER,
        )


class StaticWhatsAppService:
    async def send_text_message(self, wa_id: str, text: str):
        class Result:
            success = False
            provider_message_id = None
            raw_response = {"detail": "stub"}

        return Result()


def _wait_for_background_webhook_tasks(client, timeout: float = 5.0) -> None:
    assert client.app.state.webhook_task_coordinator.wait_until_idle(timeout)


def test_verify_meta_webhook_success(client) -> None:
    response = client.get(
        "/webhook/meta",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "change-me",
            "hub.challenge": "12345",
        },
    )

    assert response.status_code == 200
    assert response.text == "12345"


def test_receive_meta_webhook_stores_messages(client, session_maker) -> None:
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "contacts": [{"profile": {"name": "Kenji"}}],
                            "messages": [
                                {
                                    "from": "447700900125",
                                    "id": "wamid.test",
                                    "timestamp": "1741975200",
                                    "type": "text",
                                    "text": {"body": "Help"},
                                }
                            ],
                        }
                    }
                ]
            }
        ]
    }

    response = client.post("/webhook/meta", json=payload)
    assert response.status_code == 200
    assert response.json()["processed_messages"] == 1
    _wait_for_background_webhook_tasks(client)

    async def inspect() -> tuple[int, int]:
        async with session_maker() as session:
            user_count = await session.execute(select(func.count(User.id)))
            message_count = await session.execute(select(func.count(Message.id)))
            return int(user_count.scalar_one()), int(message_count.scalar_one())

    users, messages = asyncio.run(inspect())
    assert users == 1
    assert messages == 2


def test_receive_meta_webhook_ignores_empty_text_messages(client) -> None:
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "contacts": [{"profile": {"name": "Kenji"}}],
                            "messages": [
                                {
                                    "from": "447700900125",
                                    "id": "wamid.test",
                                    "timestamp": "1741975200",
                                    "type": "text",
                                    "text": {"body": "   "},
                                }
                            ],
                        }
                    }
                ]
            }
        ]
    }

    response = client.post("/webhook/meta", json=payload)
    assert response.status_code == 200
    assert response.json() == {"status": "accepted", "processed_messages": 0}
    _wait_for_background_webhook_tasks(client)


def test_receive_meta_webhook_drains_user_queue_before_reply(client, session_maker) -> None:
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "contacts": [{"profile": {"name": "Kenji"}}],
                            "messages": [
                                {
                                    "from": "447700900125",
                                    "id": "wamid.batch.1",
                                    "timestamp": "1741975200",
                                    "type": "text",
                                    "text": {"body": "I'm selling a bicycle"},
                                },
                                {
                                    "from": "447700900125",
                                    "id": "wamid.batch.2",
                                    "timestamp": "1741975201",
                                    "type": "text",
                                    "text": {"body": "25 pounds"},
                                },
                                {
                                    "from": "447700900125",
                                    "id": "wamid.batch.3",
                                    "timestamp": "1741975202",
                                    "type": "text",
                                    "text": {"body": "Headingley"},
                                },
                            ],
                        }
                    }
                ]
            }
        ]
    }

    response = client.post("/webhook/meta", json=payload)
    assert response.status_code == 200
    assert response.json()["processed_messages"] == 3
    _wait_for_background_webhook_tasks(client)

    async def inspect() -> tuple[int, int, int, Listing]:
        async with session_maker() as session:
            user_count = await session.execute(select(func.count(User.id)))
            message_count = await session.execute(select(func.count(Message.id)))
            listing_count = await session.execute(select(func.count(Listing.id)))
            listing = await session.scalar(select(Listing))
            assert listing is not None
            return (
                int(user_count.scalar_one()),
                int(message_count.scalar_one()),
                int(listing_count.scalar_one()),
                listing,
            )

    users, messages, listings, listing = asyncio.run(inspect())
    assert users == 1
    assert messages == 4
    assert listings == 1
    assert listing.title == "bicycle"
    assert listing.price == Decimal("25")
    assert listing.currency == "GBP"
    assert listing.location == "Headingley"


def test_receive_meta_webhook_deduplicates_message_ids(client, session_maker) -> None:
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "contacts": [{"profile": {"name": "Kenji"}}],
                            "messages": [
                                {
                                    "from": "447700900125",
                                    "id": "wamid.duplicate",
                                    "timestamp": "1741975200",
                                    "type": "text",
                                    "text": {"body": "Help"},
                                }
                            ],
                        }
                    }
                ]
            }
        ]
    }

    first_response = client.post("/webhook/meta", json=payload)
    second_response = client.post("/webhook/meta", json=payload)

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert first_response.json()["processed_messages"] == 1
    assert second_response.json()["processed_messages"] == 0
    _wait_for_background_webhook_tasks(client)

    async def inspect() -> tuple[int, int]:
        async with session_maker() as session:
            user_count = await session.execute(select(func.count(User.id)))
            message_count = await session.execute(select(func.count(Message.id)))
            return int(user_count.scalar_one()), int(message_count.scalar_one())

    users, messages = asyncio.run(inspect())
    assert users == 1
    assert messages == 2


def test_receive_meta_webhook_drains_out_of_order_listing_fragments(client, session_maker) -> None:
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "contacts": [{"profile": {"name": "Kenji"}}],
                            "messages": [
                                {
                                    "from": "447700900125",
                                    "id": "wamid.short.1",
                                    "timestamp": "1741975200",
                                    "type": "text",
                                    "text": {"body": "vendo"},
                                },
                                {
                                    "from": "447700900125",
                                    "id": "wamid.short.2",
                                    "timestamp": "1741975201",
                                    "type": "text",
                                    "text": {"body": "25 pounds"},
                                },
                                {
                                    "from": "447700900125",
                                    "id": "wamid.short.3",
                                    "timestamp": "1741975202",
                                    "type": "text",
                                    "text": {"body": "headingley"},
                                },
                            ],
                        }
                    }
                ]
            }
        ]
    }

    response = client.post("/webhook/meta", json=payload)
    assert response.status_code == 200
    assert response.json()["processed_messages"] == 3
    _wait_for_background_webhook_tasks(client)

    async def inspect() -> tuple[int, int, int, str]:
        async with session_maker() as session:
            user_count = await session.execute(select(func.count(User.id)))
            message_count = await session.execute(select(func.count(Message.id)))
            listing_count = await session.execute(select(func.count(Listing.id)))
            outbound_message = await session.scalar(
                select(Message.text)
                .where(Message.direction == MessageDirection.OUTBOUND)
                .order_by(Message.id.desc())
                .limit(1)
            )
            assert outbound_message is not None
            return (
                int(user_count.scalar_one()),
                int(message_count.scalar_one()),
                int(listing_count.scalar_one()),
                outbound_message,
            )

    users, messages, listings, outbound_text = asyncio.run(inspect())
    assert users == 1
    assert messages == 4
    assert listings == 0
    assert "que articulo quieres vender" in outbound_text.lower()


@pytest.mark.asyncio
async def test_receive_meta_webhook_batches_split_requests_before_reply(app, session_maker) -> None:
    settings = get_settings()
    original_burst_window = settings.inbound_message_burst_window_seconds
    settings.inbound_message_burst_window_seconds = 0.12

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as async_client:
            async def send_fragment(body: str, index: int, delay_seconds: float) -> None:
                await asyncio.sleep(delay_seconds)
                payload = {
                    "entry": [
                        {
                            "changes": [
                                {
                                    "value": {
                                        "contacts": [{"profile": {"name": "Kenji"}}],
                                        "messages": [
                                            {
                                                "from": "447700900125",
                                                "id": f"wamid.burst.{index}",
                                                "timestamp": str(1741975200 + index),
                                                "type": "text",
                                                "text": {"body": body},
                                            }
                                        ],
                                    }
                                }
                            ]
                        }
                    ]
                }

                response = await async_client.post("/webhook/meta", json=payload)
                assert response.status_code == 200
                assert response.json()["processed_messages"] == 1

            await asyncio.gather(
                send_fragment("quiero", 1, 0.00),
                send_fragment("cambiar", 2, 0.03),
                send_fragment("200 soles", 3, 0.06),
                send_fragment("por libras", 4, 0.09),
            )
            await app.state.webhook_task_coordinator.wait_for_all_tasks()

        async def inspect() -> tuple[int, int, list[str]]:
            async with session_maker() as session:
                user_count = await session.execute(select(func.count(User.id)))
                message_count = await session.execute(select(func.count(Message.id)))
                outbound_messages = await session.execute(
                    select(Message.text)
                    .where(Message.direction == MessageDirection.OUTBOUND)
                    .order_by(Message.id.asc())
                )
                return (
                    int(user_count.scalar_one()),
                    int(message_count.scalar_one()),
                    list(outbound_messages.scalars().all()),
                )

        users, messages, outbound_messages = await inspect()
        assert users == 1
        assert messages == 5
        assert len(outbound_messages) == 1
        assert "200 pen por gbp" in outbound_messages[0].lower()
        assert "en que ciudad estas" in outbound_messages[0].lower()
    finally:
        settings.inbound_message_burst_window_seconds = original_burst_window


@pytest.mark.asyncio
async def test_drain_user_queue_dispatches_reply_even_if_lock_cannot_be_released(
    session_maker,
) -> None:
    async with session_maker() as session:
        settings = get_settings()
        inbound = NormalizedInboundMessage(
            wa_id="447700900140",
            display_name="Kenji",
            text="en london",
            timestamp=datetime.now(timezone.utc),
            raw_payload={"test": True},
            message_id="wamid.lock-edge",
        )
        queue_service = StaticQueueService(inbound)
        service = WebhookService(
            session=session,
            settings=settings,
            inbound_message_queue_service=queue_service,
            message_router=StaticRouter(),
            whatsapp_service=StaticWhatsAppService(),
        )

        await service.drain_user_queue("447700900140")

        message_rows = await session.execute(select(Message.direction, Message.text).order_by(Message.id.asc()))
        rows = list(message_rows.all())

        assert rows == [
            (MessageDirection.INBOUND, "en london"),
            (MessageDirection.OUTBOUND, "processed: en london"),
        ]
