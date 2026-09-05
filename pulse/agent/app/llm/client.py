"""Thin wrapper around the Google Gemini API.

Kept to a single `complete` call -- no streaming, no tool use -- since every
current caller wants one prompt in, one text blob out. Import of the
`google-genai` package is deferred into the function so an agent checkout
without the dependency installed can still boot; the caller only pays for it if
it actually invokes the LLM.

**Every model call is metered.** `complete` is the only exported way to reach a
model from this process, and it is wrapped by `metered`, which times the call,
reads the provider's usage_metadata and writes a token_usage row -- on success
and on failure alike. A failed call has a latency cost even when it returns no
tokens, and a ledger that recorded only successes would report the cheerful half
of the bill.

The wrapper is a decorator rather than a convention because a convention is
something a new call site can forget. `_complete` is private, returns a
`Completion` rather than a string, and is not importable by accident;
tests/test_token_ledger.py asserts that no module outside this one reaches the
provider SDK directly.

Metering never fails a call: app/llm/ledger.py catches everything and writes on
a background thread. The one hard requirement is a tenant -- a model call with
no tenant in context is refused *before* it dials out, because an unattributable
row is worse than a loud error, and it is the same rule app/db.py applies to
every warehouse read.
"""

from __future__ import annotations

import functools
import time
from dataclasses import dataclass
from typing import Any, Callable

from app.config import get_settings
from app.llm import context, ledger

# Gemini 2.5 counts thinking tokens against max_output_tokens, so a budget
# sized for visible prose alone gets consumed entirely by reasoning and the
# call returns no text at all. Cap thinking well below the output ceiling so
# the response body is always reachable.
_THINKING_BUDGET = 1024


@dataclass(frozen=True)
class Completion:
    """What the provider returned, plus what it cost. Internal to this module --
    `complete` hands callers the text and lets the ledger keep the rest."""

    text: str
    model: str
    tokens_in: int = 0
    tokens_out: int = 0
    cached_tokens: int = 0


def _usage_of(response: Any) -> tuple[int, int, int]:
    """(prompt, candidate, cached) token counts from a Gemini response.

    Every field is optional and any of them can be absent or None depending on
    the model and whether a safety filter tripped, so each is read defensively.
    A missing count records as 0 -- which is a claim about what the provider
    reported, not a claim that no tokens were spent.
    """
    metadata = getattr(response, "usage_metadata", None)
    if metadata is None:
        return 0, 0, 0

    def count(*names: str) -> int:
        for name in names:
            value = getattr(metadata, name, None)
            if value is not None:
                try:
                    return int(value)
                except (TypeError, ValueError):
                    return 0
        return 0

    # thoughts_token_count is billed as output on Gemini 2.5 but reported
    # separately from candidates_token_count, so tokens_out sums both.
    tokens_out = count("candidates_token_count") + count("thoughts_token_count")
    return count("prompt_token_count"), tokens_out, count("cached_content_token_count")


def metered(fn: Callable[..., Completion]) -> Callable[..., str]:
    """Time a completion, record it, return its text.

    Wrapping is what makes the ledger unbypassable: there is no unmetered path
    to a model in this process, because the only function that reaches the SDK
    is private and this decorator is applied to the only public entry point.
    """

    @functools.wraps(fn)
    def wrapper(*args: Any, call_type: str, **kwargs: Any) -> str:
        settings = get_settings()
        model = settings.llm_model

        if not context.tenant_id():
            # Before the call, not after: an unattributable model call is a bug
            # at the call site, and letting it through would put a row in the
            # ledger that no cost query can assign to anyone.
            raise ValueError(
                "no tenant in context for a model call; set X-Tenant-Id on the request "
                "or use app.llm.context.bind(tenant_id=...)"
            )

        started = time.perf_counter()
        try:
            completion = fn(*args, **kwargs)
        except Exception as exc:
            ledger.record(ledger.Usage(
                call_type=call_type,
                model=model,
                duration_ms=_elapsed_ms(started),
                error=f"{type(exc).__name__}: {exc}",
            ))
            raise
        ledger.record(ledger.Usage(
            call_type=call_type,
            model=completion.model or model,
            tokens_in=completion.tokens_in,
            tokens_out=completion.tokens_out,
            cached_tokens=completion.cached_tokens,
            duration_ms=_elapsed_ms(started),
        ))
        return completion.text

    wrapper.__ledger_metered__ = True  # type: ignore[attr-defined]
    return wrapper


def _elapsed_ms(started: float) -> int:
    return int(round((time.perf_counter() - started) * 1000))


def _complete(system: str, prompt: str, max_tokens: int = 4096) -> Completion:
    """The raw provider call. Private: reach it through `complete`, which meters it."""
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
    tokens_in, tokens_out, cached_tokens = _usage_of(response)

    # Gemini yields no text when the candidate was blocked by a safety filter,
    # or when thinking exhausted the token budget before any prose was emitted.
    # Raise rather than return "" so the caller's retry/fallback path engages
    # instead of validating an empty narrative as if the model had answered.
    # The tokens are spent either way -- the ledger records the failure row.
    text = response.text
    if not text:
        raise RuntimeError("Gemini returned no text content")
    return Completion(text, settings.llm_model, tokens_in, tokens_out, cached_tokens)


#: One-shot completion. Raises if LLM_API_KEY is not configured, or on any
#: SDK/network failure -- callers that want graceful degradation (leadership.py's
#: template fallback, drafters.py's grounded fallback) must catch around this.
#:
#: `call_type` is keyword-only and has no useful default: it is what the cost
#: query groups by, and a ledger where every row says "other" answers nothing.
complete = metered(_complete)
