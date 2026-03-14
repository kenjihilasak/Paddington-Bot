"""Base interfaces for LLM providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.schemas.bot import ExtractionResult, IntentResult, IntentType


class LLMProvider(ABC):
    """Abstract interface for intent classification and structured extraction."""

    @abstractmethod
    async def classify_intent(
        self, message: str, context: dict[str, Any] | None = None
    ) -> IntentResult:
        """Classify a user message into a supported intent."""

    @abstractmethod
    async def extract_structured_data(
        self,
        message: str,
        context: dict[str, Any] | None = None,
        intent: IntentType | None = None,
    ) -> ExtractionResult:
        """Extract structured fields from a free-text user message."""

