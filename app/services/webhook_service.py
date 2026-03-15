"""Webhook parsing and orchestration for Meta WhatsApp inbound events."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.models import MessageDirection, MessageType
from app.db.repositories import MessageRepository, UserRepository
from app.schemas.bot import BotRouteResult, IntentType, NormalizedInboundMessage
from app.services.message_router import MessageRouter
from app.services.whatsapp_service import WhatsAppService


logger = logging.getLogger(__name__)


class WebhookService:
    """Handle Meta webhook verification and inbound message processing."""

    def __init__(
        self,
        *,
        session: AsyncSession,
        settings: Settings,
        message_router: MessageRouter,
        whatsapp_service: WhatsAppService,
    ) -> None:
        self.session = session
        self.settings = settings
        self.message_router = message_router
        self.whatsapp_service = whatsapp_service
        self.user_repository = UserRepository(session)
        self.message_repository = MessageRepository(session)

    def verify_webhook(self, mode: str | None, verify_token: str | None, challenge: str | None) -> str:
        """Validate the verification request and return the challenge string."""

        if mode != "subscribe" or verify_token != self.settings.meta_verify_token:
            raise ValueError("Webhook verification failed.")
        if challenge is None:
            raise ValueError("Missing webhook challenge.")
        return challenge

    async def handle_meta_webhook(self, payload: dict[str, Any]) -> int:
        """Process an inbound Meta webhook payload."""

        if self.settings.webhook_log_payloads:
            logger.info("Received Meta webhook payload: %s", payload)

        normalized_messages = self.extract_messages(payload)
        processed = 0
        for inbound in normalized_messages:
            await self._process_single_message(inbound)
            processed += 1
        return processed

    def extract_messages(self, payload: dict[str, Any]) -> list[NormalizedInboundMessage]:
        """Extract supported text messages from a Meta webhook payload."""

        results: list[NormalizedInboundMessage] = []
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                contacts = value.get("contacts") or []
                contact_name = None
                if contacts:
                    contact_name = contacts[0].get("profile", {}).get("name")
                for message in value.get("messages") or []:
                    if message.get("type") != "text":
                        logger.info("Ignoring unsupported inbound message type: %s", message.get("type"))
                        continue
                    wa_id = (message.get("from") or "").strip()
                    text_body = (message.get("text", {}).get("body") or "").strip()
                    if not wa_id or not text_body:
                        logger.info("Ignoring inbound message without sender id or text body.")
                        continue
                    raw_timestamp = message.get("timestamp")
                    timestamp = datetime.now(timezone.utc)
                    if raw_timestamp and str(raw_timestamp).isdigit():
                        timestamp = datetime.fromtimestamp(int(raw_timestamp), tz=timezone.utc)
                    results.append(
                        NormalizedInboundMessage(
                            wa_id=wa_id,
                            display_name=contact_name,
                            text=text_body,
                            timestamp=timestamp,
                            raw_payload=payload,
                            message_id=message.get("id"),
                            message_type=message.get("type", "text"),
                        )
                    )
        return results

    async def _process_single_message(self, inbound: NormalizedInboundMessage) -> None:
        user = await self.user_repository.upsert_whatsapp_user(inbound.wa_id, inbound.display_name)
        await self.message_repository.create(
            user_id=user.id,
            direction=MessageDirection.INBOUND,
            message_type=MessageType.TEXT,
            text=inbound.text,
            raw_payload=inbound.raw_payload,
        )
        await self.session.commit()

        try:
            route_result = await self.message_router.route_message(user=user, message_text=inbound.text)
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.exception("Message routing failed: %s", exc)
            await self.session.rollback()
            route_result = BotRouteResult(
                reply_text="Sorry, something went wrong while processing your message. Please try again.",
                intent=IntentType.UNKNOWN,
            )

        dispatch_result = await self.whatsapp_service.send_text_message(inbound.wa_id, route_result.reply_text)
        await self.message_repository.create(
            user_id=user.id,
            direction=MessageDirection.OUTBOUND,
            message_type=MessageType.TEXT,
            text=route_result.reply_text,
            raw_payload={
                "dispatch": dispatch_result.raw_response,
                "provider_message_id": dispatch_result.provider_message_id,
                "success": dispatch_result.success,
                "intent": route_result.intent.value,
            },
        )
        await self.session.commit()
