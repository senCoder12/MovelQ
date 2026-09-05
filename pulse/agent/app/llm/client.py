"""Thin wrapper around the Google Gemini API.

Kept to a single `complete` call -- no streaming, no tool use -- since
every current caller (agent/app/api/leadership.py) wants one prompt in,
one text blob out. Import of the `google-genai` package is deferred into
the function so an agent checkout without the dependency installed can
still boot; the caller only pays for it if it actually invokes the LLM.
"""

from __future__ import annotations

from app.config import get_settings

# Gemini 2.5 counts thinking tokens against max_output_tokens, so a budget
# sized for visible prose alone gets consumed entirely by reasoning and the
# call returns no text at all. Cap thinking well below the output ceiling so
# the response body is always reachable.
_THINKING_BUDGET = 1024


def complete(system: str, prompt: str, max_tokens: int = 4096) -> str:
    """One-shot completion. Raises if LLM_API_KEY is not configured, or on
    any SDK/network failure -- callers that want graceful degradation
    (e.g. leadership.py's template fallback) must catch around this."""
    settings = get_settings()
    if not settings.llm_api_key:
        raise RuntimeError("LLM_API_KEY is not configured")

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=settings.llm_api_key)
    response = client.models.generate_content(
        model=settings.llm_model,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=max_tokens,
            thinking_config=types.ThinkingConfig(thinking_budget=_THINKING_BUDGET),
        ),
    )

    # Gemini yields no text when the candidate was blocked by a safety filter,
    # or when thinking exhausted the token budget before any prose was emitted.
    # Raise rather than return "" so the caller's retry/fallback path engages
    # instead of validating an empty narrative as if the model had answered.
    text = response.text
    if not text:
        raise RuntimeError("Gemini returned no text content")
    return text
