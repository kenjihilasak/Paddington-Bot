"""Meta webhook routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse

from app.api.deps import get_webhook_service
from app.schemas.webhook import MetaWebhookProcessResponse
from app.services.webhook_service import WebhookService


router = APIRouter(prefix="/webhook/meta", tags=["webhook"])


@router.get("", response_class=PlainTextResponse)
async def verify_meta_webhook(
    hub_mode: str | None = Query(default=None, alias="hub.mode"),
    hub_verify_token: str | None = Query(default=None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(default=None, alias="hub.challenge"),
    service: WebhookService = Depends(get_webhook_service),
) -> str:
    """Verify the Meta webhook challenge."""

    try:
        return service.verify_webhook(hub_mode, hub_verify_token, hub_challenge)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("", response_model=MetaWebhookProcessResponse)
async def receive_meta_webhook(
    payload: dict[str, Any],
    service: WebhookService = Depends(get_webhook_service),
) -> MetaWebhookProcessResponse:
    """Process inbound Meta webhook payloads."""

    processed = await service.handle_meta_webhook(payload)
    return MetaWebhookProcessResponse(status="accepted", processed_messages=processed)

