"""Background queue draining for inbound webhook messages."""

from __future__ import annotations

import asyncio
import logging
import threading
import time

import httpx
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.intents.base import IntentClassifier
from app.intents.embedding_classifier import EmbeddingIntentClassifier
from app.llm.base import LLMProvider
from app.llm.openai_provider import OpenAICompatibleProvider
from app.services.conversation_state_service import ConversationStateService
from app.services.event_service import EventService
from app.services.exchange_service import ExchangeService
from app.services.inbound_message_queue_service import InboundMessageQueueService
from app.services.listing_service import ListingService
from app.services.message_router import MessageRouter
from app.services.summary_service import SummaryService
from app.services.webhook_service import WebhookService
from app.services.whatsapp_service import WhatsAppService


logger = logging.getLogger(__name__)


class WebhookTaskCoordinator:
    """Schedule queue draining in detached tasks so webhook ACKs stay fast."""

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
        redis_client: Redis,
        http_client: httpx.AsyncClient,
    ) -> None:
        self.session_factory = session_factory
        self.settings = settings
        self.redis_client = redis_client
        self.http_client = http_client
        self._tasks: set[asyncio.Task[None]] = set()
        self._condition = threading.Condition()
        self._active_task_count = 0

    def schedule_user_drain(self, wa_id: str) -> None:
        """Schedule background queue processing for a WhatsApp user."""

        with self._condition:
            self._active_task_count += 1

        task = asyncio.create_task(self._run_user_drain(wa_id))
        self._tasks.add(task)
        task.add_done_callback(self._handle_task_completion)

    async def wait_for_all_tasks(self) -> None:
        """Wait for currently scheduled tasks to finish on the same event loop."""

        while self._tasks:
            pending = tuple(self._tasks)
            await asyncio.gather(*pending, return_exceptions=True)

    def wait_until_idle(self, timeout: float = 5.0) -> bool:
        """Block the current thread until no scheduled tasks remain."""

        deadline = time.monotonic() + timeout
        with self._condition:
            while self._active_task_count > 0:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._condition.wait(timeout=remaining)
        return True

    async def _run_user_drain(self, wa_id: str) -> None:
        try:
            async with self.session_factory() as session:
                webhook_service = self._build_webhook_service(session)
                await webhook_service.drain_user_queue(wa_id)
        except Exception:  # pragma: no cover - defensive logging
            logger.exception("Detached webhook drain failed for wa_id=%s", wa_id)

    def _handle_task_completion(self, task: asyncio.Task[None]) -> None:
        self._tasks.discard(task)

        try:
            task.result()
        except Exception:  # pragma: no cover - logged above in task body
            logger.exception("Webhook background task finished with an error.")

        with self._condition:
            self._active_task_count = max(0, self._active_task_count - 1)
            self._condition.notify_all()

    def _build_webhook_service(self, session: AsyncSession) -> WebhookService:
        conversation_state_service = ConversationStateService(self.redis_client, session, self.settings)
        message_router = MessageRouter(
            settings=self.settings,
            conversation_state_service=conversation_state_service,
            exchange_service=ExchangeService(session, self.settings),
            listing_service=ListingService(session, self.settings),
            event_service=EventService(session),
            summary_service=SummaryService(session, self.settings),
            intent_classifier=self._build_intent_classifier(),
            llm_provider=self._build_llm_provider(),
        )
        return WebhookService(
            session=session,
            settings=self.settings,
            inbound_message_queue_service=InboundMessageQueueService(self.redis_client, self.settings),
            message_router=message_router,
            whatsapp_service=WhatsAppService(self.settings, self.http_client),
        )

    def _build_intent_classifier(self) -> IntentClassifier | None:
        if not self.settings.is_intent_classifier_configured:
            return None
        return EmbeddingIntentClassifier(self.settings, self.http_client)

    def _build_llm_provider(self) -> LLMProvider | None:
        if not self.settings.is_llm_configured:
            return None
        return OpenAICompatibleProvider(self.settings, self.http_client)
