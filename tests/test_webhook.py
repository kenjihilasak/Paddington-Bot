"""Webhook endpoint tests."""

from __future__ import annotations

import asyncio

from sqlalchemy import func, select

from app.db.models import Message, User


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
