"""Thin wrapper around the Anthropic Messages API.

Kept to a single `complete` call -- no streaming, no tool use -- since
every current caller (agent/app/api/leadership.py) wants one prompt in,
one text blob out. Import of the `anthropic` package is deferred into
the function so an agent checkout without the dependency installed can
still boot; the caller only pays for it if it actually invokes the LLM.
"""

from __future__ import annotations

from app.config import get_settings


def complete(system: str, prompt: str, max_tokens: int = 1024) -> str:
    """One-shot completion. Raises if LLM_API_KEY is not configured, or on
    any SDK/network failure -- callers that want graceful degradation
    (e.g. leadership.py's template fallback) must catch around this."""
    settings = get_settings()
    if not settings.llm_api_key:
        raise RuntimeError("LLM_API_KEY is not configured")

    import anthropic

    client = anthropic.Anthropic(api_key=settings.llm_api_key)
    response = client.messages.create(
        model=settings.llm_model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in response.content if block.type == "text")
