"""OpenAI-compatible LLM provider implementation."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import Settings
from app.llm.base import LLMProvider
from app.llm.parser import extract_json_object
from app.llm.prompts import build_extraction_system_prompt, build_intent_system_prompt
from app.schemas.bot import ExtractionResult, IntentResult, IntentType


logger = logging.getLogger(__name__)


class OpenAICompatibleProvider(LLMProvider):
    """LLM provider that uses an OpenAI-compatible chat completions endpoint."""

    def __init__(self, settings: Settings, http_client: httpx.AsyncClient) -> None:
        self.settings = settings
        self.http_client = http_client

    async def classify_intent(
        self, message: str, context: dict[str, Any] | None = None
    ) -> IntentResult:
        payload = await self._chat_completion(
            system_prompt=build_intent_system_prompt(),
            user_payload={"message": message, "context": context or {}},
        )
        return IntentResult.model_validate(payload)

    async def extract_structured_data(
        self,
        message: str,
        context: dict[str, Any] | None = None,
        intent: IntentType | None = None,
    ) -> ExtractionResult:
        payload = await self._chat_completion(
            system_prompt=build_extraction_system_prompt(intent),
            user_payload={
                "message": message,
                "context": context or {},
                "intent": intent.value if intent else None,
            },
        )
        return ExtractionResult.model_validate(payload)

    async def _chat_completion(
        self, *, system_prompt: str, user_payload: dict[str, Any]
    ) -> dict[str, Any]:
        url = f"{self.settings.llm_base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.settings.llm_api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self.settings.llm_model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": str(user_payload)},
            ],
        }
        response = await self.http_client.post(
            url,
            headers=headers,
            json=body,
            timeout=self.settings.llm_timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        parsed = extract_json_object(content)
        logger.debug("Parsed LLM response: %s", parsed)
        return parsed
