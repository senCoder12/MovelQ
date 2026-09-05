"""POST /internal/leadership-narrative -- LLM-authored prose for the
leadership pack.

Java assembles every structured field (scope, tiles, per-finding
metrics, footer); this endpoint's only job is headline + summary +
per-finding body/recommendation. Every number in that prose must trace
back to a number in the request -- app/agent/validator.py enforces it.
One retry on an ungrounded number, then a template fallback that
renders the structured fields with no prose at all, so the pack is
still forwardable even when the LLM path is down or misbehaving.

Responses are cached on a hash of the request payload: the same period
assembled from the same underlying data should not re-spend an LLM call
on every dashboard refresh. Only a validated (or fallback-free) success
is cached -- a fallback is not, so a transient LLM failure doesn't
permanently pin a request to the no-prose rendering.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter

from app.agent import validator
from app.llm import client as llm_client

router = APIRouter(prefix="/internal", tags=["internal"])

_PROMPT_PATH = Path(__file__).resolve().parents[1] / "agent" / "prompts" / "leadership_pack.md"
_CACHE: dict[str, dict[str, Any]] = {}


def _prompt_template() -> str:
    return _PROMPT_PATH.read_text()


def _cache_key(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _parse_json(text: str) -> dict[str, Any] | None:
    """Strict JSON parse. Strips a markdown fence defensively even though
    the prompt forbids one -- LLMs wrap output in ```json fences often
    enough that failing outright would waste the one retry we get."""
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


def _call_llm(payload: dict[str, Any], feedback: str | None = None) -> dict[str, Any] | None:
    prompt = _prompt_template() + "\n\n## Input\n\n" + json.dumps(payload, indent=2)
    if feedback:
        prompt += f"\n\n## Correction required\n\n{feedback}"
    try:
        raw = llm_client.complete(system="Respond with strict JSON only, no markdown fences.", prompt=prompt)
    except Exception:
        # Any LLM-call failure (missing key, network, rate limit) degrades to
        # the template fallback rather than a 500 -- see module docstring.
        return None
    return _parse_json(raw)


def _fallback(payload: dict[str, Any]) -> dict[str, Any]:
    """Structured-fields-only rendering: no prose, so nothing here can be ungrounded."""
    period = payload.get("period", "this period")
    tiles = payload.get("tiles") or []
    tile_line = "; ".join(f"{t.get('label')}: {t.get('value')}" for t in tiles) or "no tiles supplied"

    findings = []
    for f in payload.get("findings") or []:
        metric = f.get("metric") or {}
        unit = metric.get("unit", "")
        unit_suffix = "%" if unit in ("%", "percent") else f" {unit}" if unit else ""
        findings.append(
            {
                "insight_id": f.get("insight_id"),
                "body": f"{metric.get('name', 'Metric')}: {metric.get('value')}{unit_suffix} (n={metric.get('n')}).",
                "recommendation": "Review this finding with the operations team.",
            }
        )

    headline = f"Leadership pack for {period}: structured summary (narrative generation unavailable)"
    return {
        "headline": headline[:100],
        "summary": f"Figures for {period}: {tile_line}.",
        "findings": findings,
    }


@router.post("/leadership-narrative")
def leadership_narrative(payload: dict[str, Any]) -> dict[str, Any]:
    key = _cache_key(payload)
    if key in _CACHE:
        return _CACHE[key]

    parsed = _call_llm(payload)
    if parsed is not None:
        result = validator.validate(payload, parsed)
        if result.ok:
            _CACHE[key] = parsed
            return parsed

        feedback = (
            "Your previous response used numbers that do not appear in the input: "
            f"{sorted(result.ungrounded)}. Regenerate, citing only numbers present in the input above."
        )
        retry = _call_llm(payload, feedback=feedback)
        if retry is not None and validator.validate(payload, retry).ok:
            _CACHE[key] = retry
            return retry

    return _fallback(payload)
