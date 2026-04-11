"""Embedding-based intent classifier using an OpenAI-compatible embeddings API."""

from __future__ import annotations

import math
from typing import Any

import httpx

from app.core.config import Settings
from app.intents.base import IntentClassifier
from app.intents.examples import INTENT_EXAMPLES
from app.schemas.bot import IntentResult, IntentType


class EmbeddingIntentClassifier(IntentClassifier):
    """Classify intents by comparing a message embedding against intent examples."""

    def __init__(self, settings: Settings, http_client: httpx.AsyncClient) -> None:
        self.settings = settings
        self.http_client = http_client

    async def classify_intent(self, message: str) -> IntentResult:
        example_items: list[tuple[IntentType, str]] = []
        for intent, examples in INTENT_EXAMPLES.items():
            for example in examples:
                example_items.append((intent, example))

        payload_inputs = [self._format_query(message)]
        payload_inputs.extend(self._format_document(example) for _, example in example_items)
        embeddings = await self._embed_texts(payload_inputs)
        query_vector = embeddings[0]

        best_intent = IntentType.UNKNOWN
        best_score = -1.0
        for index, (intent, _) in enumerate(example_items, start=1):
            score = self._cosine_similarity(query_vector, embeddings[index])
            if score > best_score:
                best_score = score
                best_intent = intent

        if best_score < self.settings.intent_classifier_threshold:
            return IntentResult(intent=IntentType.UNKNOWN, confidence=max(best_score, 0.0), source="embedding")

        return IntentResult(intent=best_intent, confidence=max(best_score, 0.0), source="embedding")

    async def _embed_texts(self, inputs: list[str]) -> list[list[float]]:
        url = f"{self.settings.intent_classifier_base_url.rstrip('/')}/embeddings"
        headers = {"Content-Type": "application/json"}
        if self.settings.intent_classifier_api_key:
            headers["Authorization"] = f"Bearer {self.settings.intent_classifier_api_key}"

        response = await self.http_client.post(
            url,
            headers=headers,
            json={"model": self.settings.intent_classifier_model, "input": inputs},
            timeout=self.settings.intent_classifier_timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        data = payload.get("data")
        if not isinstance(data, list) or len(data) != len(inputs):
            raise ValueError("Embedding response did not match the number of requested inputs.")

        embeddings: list[list[float]] = []
        for item in sorted(data, key=lambda candidate: candidate.get("index", 0)):
            vector = item.get("embedding")
            if not isinstance(vector, list):
                raise ValueError("Embedding response item is missing a vector.")
            embeddings.append([float(value) for value in vector])
        return embeddings

    @staticmethod
    def _format_query(text: str) -> str:
        return f"query: {text.strip()}"

    @staticmethod
    def _format_document(text: str) -> str:
        return f"passage: {text.strip()}"

    @staticmethod
    def _cosine_similarity(left: list[float], right: list[float]) -> float:
        numerator = sum(left_value * right_value for left_value, right_value in zip(left, right))
        left_norm = math.sqrt(sum(value * value for value in left))
        right_norm = math.sqrt(sum(value * value for value in right))
        if left_norm == 0.0 or right_norm == 0.0:
            return 0.0
        return numerator / (left_norm * right_norm)
