"""Logging configuration helpers."""

from __future__ import annotations

import logging


def configure_logging(debug: bool = False) -> None:
    """Configure basic structured logging for the application."""

    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
