"""Shared strict-JSON parsing for LLM completions.

Every prompt in this app (leadership_pack.md, draft_action.md) forbids a
markdown fence around the JSON it returns, but LLMs wrap output in ```json
fences often enough that failing outright on one would waste a retry --
both callers strip it defensively before parsing.
"""

from __future__ import annotations

import json
from typing import Any


def parse_json_object(text: str) -> dict[str, Any] | None:
    """Strict JSON object parse, tolerant of a wrapping markdown fence."""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.lower().startswith("json"):
            stripped = stripped[4:]
        stripped = stripped.strip()
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None
