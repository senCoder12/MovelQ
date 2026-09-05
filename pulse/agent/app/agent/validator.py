"""Grounding validator for LLM-authored narrative JSON.

Every number in an LLM narrative field must trace back to a number
already present in the structured input it was given -- the LLM is
allowed to describe the input, never to compute, estimate, or re-round
a figure (a 60.8% coverage rate written back as "61%" is exactly the
kind of drift this exists to catch).

Numbers are extracted from both sides with the same regex, so a display
string like "215,885" or "8.11%" in the input lines up with the same
text appearing in the output. Indian/British business-register
abbreviations (2.87M, 1.2Cr, 40L) are expanded to their full value
before comparison, since a finding may cite "₹2.87M" for an input value
carried as a raw 2870000.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# Optional suffix must immediately follow the digits (no word boundary in
# between), so "2.87M" matches but "2.87 million" does not -- spelled-out
# multipliers are rare enough in generated prose that treating them as a
# miss (retry-worthy) is safer than guessing at a word list.
_NUMBER_RE = re.compile(r"(?<![\w.])[+-]?\d[\d,]*\.?\d*(cr|crore|lakh|l|k|m)?", re.IGNORECASE)

_SUFFIX_MULTIPLIER = {
    "k": 1_000,
    "m": 1_000_000,
    "l": 100_000,
    "lakh": 100_000,
    "cr": 10_000_000,
    "crore": 10_000_000,
}


def _normalise(raw: str, suffix: str | None) -> float | None:
    cleaned = raw.replace(",", "").strip()
    if not cleaned or cleaned in {"+", "-", "."}:
        return None
    try:
        value = float(cleaned)
    except ValueError:
        return None
    if suffix:
        value *= _SUFFIX_MULTIPLIER[suffix.lower()]
    return value


def extract_numbers(text: str) -> set[float]:
    """Every number mentioned in a piece of text, suffix-expanded."""
    numbers: set[float] = set()
    for match in _NUMBER_RE.finditer(text):
        suffix = match.group(1)
        raw = match.group(0)
        if suffix:
            raw = raw[: -len(suffix)]
        value = _normalise(raw, suffix)
        if value is not None:
            numbers.add(round(value, 6))
    return numbers


def collect_input_numbers(value: Any) -> set[float]:
    """Every number reachable from the structured request payload.

    Walks dicts/lists and pulls numbers out of both numeric leaves and
    strings -- tiles carry pre-formatted display strings ("215,885",
    "8.11%") rather than raw numerics, so both forms must be scanned.
    """
    numbers: set[float] = set()
    if isinstance(value, dict):
        for v in value.values():
            numbers |= collect_input_numbers(v)
    elif isinstance(value, list):
        for v in value:
            numbers |= collect_input_numbers(v)
    elif isinstance(value, bool):
        pass  # bool is a subclass of int -- exclude before the int/float branch
    elif isinstance(value, (int, float)):
        numbers.add(round(float(value), 6))
    elif isinstance(value, str):
        numbers |= extract_numbers(value)
    return numbers


_NARRATIVE_TEXT_FIELDS = ("headline", "summary")
_FINDING_TEXT_FIELDS = ("body", "recommendation")


@dataclass
class ValidationResult:
    ok: bool
    ungrounded: set[float] = field(default_factory=set)


def validate_text(grounded_source: Any, *texts: str) -> ValidationResult:
    """Check every number across `texts` traces back to a number reachable
    from `grounded_source`. The shared primitive behind both `validate`
    (leadership-narrative JSON) and `validate_action` (an action draft's
    subject + body) -- both are "some free text an LLM wrote against a
    structured input" and the grounding rule is identical either way.
    """
    grounded = collect_input_numbers(grounded_source)
    produced: set[float] = set()
    for text in texts:
        produced |= extract_numbers(text or "")
    ungrounded = {n for n in produced if not _has_match(n, grounded)}
    return ValidationResult(ok=not ungrounded, ungrounded=ungrounded)


def validate(input_payload: Any, output: dict[str, Any]) -> ValidationResult:
    """Check every number in `output` (the parsed leadership-narrative JSON)
    traces back to a number in `input_payload` (the request Java sent).
    """
    texts = [str(output.get(field_name, "")) for field_name in _NARRATIVE_TEXT_FIELDS]
    for finding in output.get("findings", []) or []:
        for field_name in _FINDING_TEXT_FIELDS:
            texts.append(str(finding.get(field_name, "")))
    return validate_text(input_payload, *texts)


def validate_action(insight: dict[str, Any], subject: str, body: str) -> ValidationResult:
    """Check every number in an action draft's subject + body traces back to
    a number in the source InsightPacket. An action with an ungrounded figure
    is a bug -- see agent/app/actions/drafters.py for the retry/fallback that
    enforces this before a draft is ever returned.
    """
    return validate_text(insight, subject, body)


def _has_match(value: float, grounded: set[float]) -> bool:
    return any(abs(value - g) < 1e-6 for g in grounded)
