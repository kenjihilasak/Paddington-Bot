"""Outbound Meta WhatsApp Cloud API service."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import Settings


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class WhatsAppDispatchResult:
    """Result of an outbound WhatsApp send attempt."""

    success: bool
    provider_message_id: str | None
    raw_response: dict[str, Any]


class WhatsAppService:
    """Send outbound WhatsApp messages using the Meta Graph API."""

    def __init__(self, settings: Settings, http_client: httpx.AsyncClient) -> None:
        self.settings = settings
        self.http_client = http_client

    async def send_text_message(self, wa_id: str, text: str) -> WhatsAppDispatchResult:
        """Send a text message to a WhatsApp user."""

        if not self.settings.is_meta_configured:
            logger.warning("Meta credentials are not configured. Outbound message was not sent.")
            return WhatsAppDispatchResult(
                success=False,
                provider_message_id=None,
                raw_response={"detail": "Meta credentials are not configured."},
            )

        url = (
            f"https://graph.facebook.com/{self.settings.meta_graph_version}/"
            f"{self.settings.meta_phone_number_id}/messages"
        )
        payload = {
            "messaging_product": "whatsapp",
            "to": wa_id,
            "type": "text",
            "text": {"preview_url": False, "body": text},
        }
        headers = {
            "Authorization": f"Bearer {self.settings.meta_access_token}",
            "Content-Type": "application/json",
        }
        try:
            response = await self.http_client.post(url, headers=headers, json=payload, timeout=15.0)
            response.raise_for_status()
            data = response.json()
            provider_message_id = None
            messages = data.get("messages") or []
            if messages:
                provider_message_id = messages[0].get("id")
            return WhatsAppDispatchResult(
                success=True,
                provider_message_id=provider_message_id,
                raw_response=data,
            )
        except httpx.HTTPError as exc:
            logger.exception("Failed to send outbound WhatsApp message: %s", exc)
            return WhatsAppDispatchResult(
                success=False,
                provider_message_id=None,
                raw_response={"detail": str(exc)},
            )

