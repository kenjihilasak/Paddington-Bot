"""Base interfaces for intent classification providers."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.schemas.bot import IntentResult


class IntentClassifier(ABC):
    """Abstract interface for intent classifiers."""

    @abstractmethod
    async def classify_intent(self, message: str) -> IntentResult:
        """Classify a user message into a supported intent."""
