"""FastAPI application entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from redis.asyncio import Redis

from app.api.routes import events, exchange_offers, health, listings, summary, webhook
from app.core.config import get_settings
from app.core.logging import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create and clean up shared clients."""

    settings = get_settings()
    configure_logging(settings.debug)
    app.state.redis = Redis.from_url(settings.redis_url, decode_responses=False)
    app.state.http_client = httpx.AsyncClient()
    try:
        yield
    finally:
        await app.state.http_client.aclose()
        await app.state.redis.aclose()


def create_app() -> FastAPI:
    """Create the FastAPI application."""

    settings = get_settings()
    app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)
    app.include_router(health.router)
    app.include_router(exchange_offers.router)
    app.include_router(listings.router)
    app.include_router(events.router)
    app.include_router(summary.router)
    app.include_router(webhook.router)
    return app


app = create_app()
