"""Webhook response schemas."""

from __future__ import annotations

from pydantic import BaseModel


class MetaWebhookProcessResponse(BaseModel):
    """Result of processing an inbound Meta webhook."""

    status: str
    processed_messages: int

