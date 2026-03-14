"""Parsing helpers for structured LLM responses."""

from __future__ import annotations

import json


def extract_json_object(raw_text: str) -> dict:
    """Extract a JSON object from a model response."""

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        start = raw_text.find("{")
        end = raw_text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        return json.loads(raw_text[start : end + 1])

