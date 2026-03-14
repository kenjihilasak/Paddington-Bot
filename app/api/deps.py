"""Dependency wiring for API routes."""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
from fastapi import Depends, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.llm.base import LLMProvider
from app.llm.openai_provider import OpenAICompatibleProvider
from app.services.conversation_state_service import ConversationStateService
from app.services.event_service import EventService
from app.services.exchange_service import ExchangeService
from app.services.listing_service import ListingService
from app.services.message_router import MessageRouter
from app.services.summary_service import SummaryService
from app.services.webhook_service import WebhookService
from app.services.whatsapp_service import WhatsAppService


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """Yield the current request database session."""

    async for session in get_session():
        yield session


def get_app_settings() -> Settings:
    """Return application settings."""

    return get_settings()


async def get_redis_client(request: Request) -> Redis:
    """Return the shared Redis client."""

    return request.app.state.redis


async def get_http_client(request: Request) -> httpx.AsyncClient:
    """Return the shared HTTP client."""

    return request.app.state.http_client


async def get_llm_provider(
    settings: Settings = Depends(get_app_settings),
    http_client: httpx.AsyncClient = Depends(get_http_client),
) -> LLMProvider | None:
    """Return the configured LLM provider if credentials are available."""

    if not settings.is_llm_configured:
        return None
    return OpenAICompatibleProvider(settings, http_client)


async def get_exchange_service(
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
) -> ExchangeService:
    return ExchangeService(session, settings)


async def get_listing_service(
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
) -> ListingService:
    return ListingService(session, settings)


async def get_event_service(session: AsyncSession = Depends(get_db_session)) -> EventService:
    return EventService(session)


async def get_summary_service(
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
) -> SummaryService:
    return SummaryService(session, settings)


async def get_conversation_state_service(
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
    redis_client: Redis = Depends(get_redis_client),
) -> ConversationStateService:
    return ConversationStateService(redis_client, session, settings)


async def get_message_router(
    settings: Settings = Depends(get_app_settings),
    conversation_state_service: ConversationStateService = Depends(get_conversation_state_service),
    exchange_service: ExchangeService = Depends(get_exchange_service),
    listing_service: ListingService = Depends(get_listing_service),
    event_service: EventService = Depends(get_event_service),
    summary_service: SummaryService = Depends(get_summary_service),
    llm_provider: LLMProvider | None = Depends(get_llm_provider),
) -> MessageRouter:
    return MessageRouter(
        settings=settings,
        conversation_state_service=conversation_state_service,
        exchange_service=exchange_service,
        listing_service=listing_service,
        event_service=event_service,
        summary_service=summary_service,
        llm_provider=llm_provider,
    )


async def get_whatsapp_service(
    settings: Settings = Depends(get_app_settings),
    http_client: httpx.AsyncClient = Depends(get_http_client),
) -> WhatsAppService:
    return WhatsAppService(settings, http_client)


async def get_webhook_service(
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
    message_router: MessageRouter = Depends(get_message_router),
    whatsapp_service: WhatsAppService = Depends(get_whatsapp_service),
) -> WebhookService:
    return WebhookService(
        session=session,
        settings=settings,
        message_router=message_router,
        whatsapp_service=whatsapp_service,
    )

