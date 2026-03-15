"""Service-layer exceptions."""

from __future__ import annotations


class ResourceNotFoundError(ValueError):
    """Raised when a required database record does not exist."""

