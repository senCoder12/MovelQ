"""One conversational turn, end to end.

Resolve the packet, classify the question, render the answer, optionally
re-phrase it, and hand back something the caller can both display and log.
No state lives here: the caller supplies the history, and the caller persists
the turn. Chat has no memory of its own across sessions and is not supposed to.
"""

from __future__ import annotations

import time
from typing import Any

from app.chat import facts as chat_facts
from app.chat import router as chat_router
from app.chat import templates
from app.detect import signals

#: History is capped at this many turns and carries intent labels and answers
#: only -- never the packet. The router reads the labels for pronoun-shaped
#: follow-ups ("and the vendor?"); nothing else reads history at all.
MAX_HISTORY_TURNS = 6

#: Enriched packets are cached for one short conversation, keyed by tenant,
#: insight and window. A chat is several questions about one finding in a row,
#: and re-slicing the metric for each of them is work the first question
#: already did. Short enough that a refresh mid-conversation is picked up.
_CACHE_TTL_SECONDS = 120
_CACHE: dict[tuple[str, str, str], tuple[float, dict[str, Any]]] = {}


def trim_history(history: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """The last few turns, stripped to what the router may see."""
    kept = []
    for turn in (history or [])[-MAX_HISTORY_TURNS:]:
        if not isinstance(turn, dict):
            continue
        kept.append(
            {
                "role": turn.get("role"),
                "intent": turn.get("intent"),
                "message": turn.get("message") or turn.get("answer"),
            }
        )
    return kept


def resolve_insight(
    insight_id: str, tenant_id: str, insight: dict[str, Any] | None = None
) -> dict[str, Any] | None:
    """The packet this conversation is about, enriched with chat facts.

    The caller normally passes the packet it already has -- the same object it
    rendered on the card -- and this only adds the chat extras. When it does
    not, detection is re-run for the tenant and the insight picked out by id,
    which costs a warehouse pass and is why the result is cached.
    """
    if insight is not None:
        return chat_facts.build(insight)

    key = (tenant_id, insight_id, "detected")
    cached = _CACHE.get(key)
    if cached is not None and time.time() - cached[0] < _CACHE_TTL_SECONDS:
        return cached[1]

    for candidate in signals.detect_tenant(tenant_id):
        if candidate["insight_id"] == insight_id:
            enriched = chat_facts.build(candidate)
            _CACHE[key] = (time.time(), enriched)
            return enriched
    return None


def answer(
    insight: dict[str, Any],
    message: str,
    history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Classify one message and answer it from the packet.

    ``insight`` must already carry ``chat_facts`` (see resolve_insight). The
    returned object is the API response plus a ``routing`` block the endpoint
    logs and the UI ignores.
    """
    trimmed = trim_history(history)
    route = chat_router.route(message, insight, trimmed)
    rendered = templates.render(insight, route.intent, route.slots)
    polished, polish_meta = templates.polish(insight, rendered, message)

    return {
        **polished,
        "confidence": round(route.confidence, 2),
        "slots": route.slots,
        "routing": {
            "source": route.source,
            "note": route.note,
            "phrasing": polish_meta["reason"],
            "phrased_by_model": polish_meta["polished"],
            "tokens_in": route.tokens_in + polish_meta["tokens_in"],
            "tokens_out": route.tokens_out + polish_meta["tokens_out"],
        },
    }


def starters(insight: dict[str, Any]) -> list[str]:
    """Three opening questions for *this* insight, not three generic ones.

    Built from what the packet actually carries: the control most likely to be
    the first objection, the sample question, and row examples where a
    whitelisted view exists. Shown above the input on first open.
    """
    facts = insight.get("chat_facts") or {}
    chips: list[str] = []

    vendor = chat_facts.control_for(facts, "vendor")
    if vendor is not None:
        chips.append("Couldn't this be the vendor?")
    else:
        top = (insight.get("attribution") or [{}])[0]
        if top.get("value"):
            chips.append(f"How does {top['value']} compare to the others?")

    chips.append("Is the sample large enough?")

    if (facts.get("examples") or {}).get("available"):
        chips.append("Show me some of these trips")
    else:
        chips.append("What do you recommend?")
    return chips[:3]
