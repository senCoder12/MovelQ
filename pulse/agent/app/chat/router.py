"""Which of the eight questions was asked, and with what slots.

One cheap model call. It is given the user's message and a compact summary of
the insight -- metric name, entity, which attribution dimensions exist, which
controls were run -- never the full packet. It returns strict JSON and nothing
else:

    {"intent": "...", "slots": {...}, "confidence": 0.0-1.0}

It produces no prose, no numbers and no explanation, because it is not the
thing that answers; app/chat/templates.py is. Below MIN_CONFIDENCE the answer
is discarded and the question is refused.

Behind the model call sits a rule router, and it is not a stub. It is the only
router when pulse.llm.enabled is false -- chat has to answer all eight intents
from templates in that mode -- and it is the fallback whenever the model call
fails, returns nothing parseable, or comes back under confidence. eval/ runs
the full golden set through it on every change.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.agent.json_llm import parse_json_object
from app.chat import facts as chat_facts
from app.chat import intents
from app.config import get_settings
from app.llm import client as llm_client

_PROMPT_PATH = Path(__file__).resolve().parents[1] / "agent" / "prompts" / "route_intent.md"

#: Ceiling on the model's half of the router budget. The prompt is a fixed
#: template plus a summary of one insight, and the reply is a three-key object.
MAX_ROUTER_OUTPUT_TOKENS = 80


@dataclass
class Route:
    intent: str
    slots: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    #: "model" | "rules" | "model-then-rules" -- logged, and shown nowhere.
    source: str = "rules"
    tokens_in: int = 0
    tokens_out: int = 0
    note: str = ""


# --- the compact insight summary ---------------------------------------------

def summarise(insight: dict[str, Any]) -> dict[str, Any]:
    """What the router is allowed to see.

    Deliberately small: names and labels, no figures. The router decides which
    question was asked, and a number in its input is a number it might put in
    its output -- which is not its job, and is a rule the prompt can state more
    convincingly when the input has none to reach for.
    """
    metric = insight.get("metric") or {}
    entity = insight.get("entity") or {}
    facts = insight.get("chat_facts") or {}
    return {
        "metric": metric.get("name"),
        "entity": entity.get("name"),
        "attribution_dimensions": sorted(
            {entry.get("dim_label") or entry.get("dim") for entry in facts.get("attribution_ranked") or []}
            or {entry.get("dim") for entry in insight.get("attribution") or []}
        ),
        "named_contributors": [
            entry.get("value") for entry in (facts.get("attribution_ranked") or insight.get("attribution") or [])
        ][:8],
        "controls_run": chat_facts.tested_control_labels(facts)
        or [entry.get("control") for entry in insight.get("controls") or []],
        "row_examples_available": bool((facts.get("examples") or {}).get("available")),
    }


# --- rule router --------------------------------------------------------------

#: Phrase -> intent, checked in order. Ordering matters where a message could
#: match two: "is this just the vendor" is a control challenge, not a request
#: to compare that vendor, because the objection is the question.
_RULES: tuple[tuple[str, str], ...] = (
    # OUT_OF_SCOPE first: a question about weather or every vendor in the fleet
    # must not be rescued by a later keyword.
    (r"\b(weather|rain|traffic condition|news|joke|who are you|your name|model are you)\b", "OUT_OF_SCOPE"),
    (r"\b(all (our|the) (vendors|offices|sites|insights|tenants)|every (vendor|office|insight)|"
     r"across (all|every) (vendors|insights|tenants)|fleet[- ]wide summary|summari[sz]e (all|our|every))\b",
     "OUT_OF_SCOPE"),
    (r"\b(last (quarter|month|year)|next (quarter|month|year)|forecast|predict|chart|graph|plot|"
     r"write .*sql|run a query)\b", "OUT_OF_SCOPE"),

    (r"\b(show|give|list|see|pull|display)\b.{0,30}\b(trip|trips|row|rows|record|records|example|examples|sample)\b",
     "SHOW_ME_EXAMPLES"),
    (r"\b(examples|sample rows|raw rows|underlying (rows|trips|data))\b", "SHOW_ME_EXAMPLES"),

    (r"\b(couldn'?t|could'?nt|isn'?t|is'?nt|not just|probably just|surely just|just|only|merely)\b"
     r".{0,40}\b(vendor|vendors|driver|drivers|traffic|evening|morning|night|afternoon|hour|hours|"
     r"time of day|shift|office|offices|site|sites|route|weather)\b", "CONTROL_CHALLENGE"),
    (r"\b(how do (you|we) know (it'?s|it is|this is|that is|its|thats) not|what if it'?s|"
     r"explained by|confounded|confound|controll?ed for|control for|rule out|ruled out|"
     r"account(ed)? for (the )?(vendor|hour|office|time))\b", "CONTROL_CHALLENGE"),

    (r"\b(sample|sample size|\d[\d,]* (trips|rows|records|of them) enough|enough (trips|rows|"
     r"data|records|of them)|big enough|large enough|statistically|significan(t|ce)|noise|random|"
     r"chance|prove it|how sure|how confident|trust (this|these|that|the number))\b",
     "IS_SAMPLE_SUFFICIENT"),
    # "enough" on its own, once the phrases above have had their turn: in this
    # drawer it is always a question about sample size.
    (r"\benough\b", "IS_SAMPLE_SUFFICIENT"),

    (r"\b(excluded|exclusion|thr(ow|ew|own) (it )?away|dropped rows|bad data|dirty data|"
     r"data quality|if the data (is|were) wrong|garbage|missing (data|rows)|dq)\b",
     "WHAT_IF_DATA_WRONG"),

    (r"\b(when did|since when|how long|start(ed)?|began|begin|onset|trend|change point|"
     r"new problem|always been)\b", "WHEN_DID_IT_START"),

    (r"\b(why (is |are )?(this|that|the|it)|why not (the )?(vendor|office|shift|route)|"
     r"how did you (decide|pick|choose)|dimension|not the vendor|rather than the)\b",
     "WHY_THIS_DIMENSION"),

    (r"\b(what should|what do you recommend|recommend|recommendation|what next|next step|"
     r"what would you do|what do i do|advice|suggest)\b", "WHAT_SHOULD_I_DO"),

    (r"\b(compare|versus|vs\.?|how does .* compare|what about|worse than|better than|"
     r"against the others|relative to)\b", "COMPARE_ENTITY"),
)

#: Objection words -> the control they name. Deliberately narrow: "driver" is
#: not mapped to vendor, because drivers were not tested and answering a driver
#: question with the vendor control would be a claim we did not check.
_CONTROL_WORDS: tuple[tuple[str, str], ...] = (
    (r"\bvendor|supplier|operator", "vendor"),
    (r"\bevening|morning|night|afternoon|hour|time of day|peak|shift bucket|rush", "hour"),
    (r"\boffice|site|location|branch|depot", "office"),
)

_LIMIT_RE = re.compile(r"\b(\d{1,3})\b")

#: Rule-router confidence. Not a probability -- a statement about how the match
#: was made, so MIN_CONFIDENCE means the same thing whichever router ran.
_CONFIDENCE_PHRASE = 0.75      # matched a phrase rule
_CONFIDENCE_ENTITY = 0.7       # matched a named contributor in the packet
_CONFIDENCE_NONE = 0.2         # matched nothing; refused


def _extract_limit(message: str) -> int | None:
    for match in _LIMIT_RE.finditer(message):
        value = int(match.group(1))
        if 1 <= value <= intents.EXAMPLES_MAX_LIMIT:
            return value
    return None


def _extract_control_name(message: str) -> str:
    for pattern, name in _CONTROL_WORDS:
        if re.search(pattern, message, re.IGNORECASE):
            return name
    return "other"


#: A capitalised name or a shift-style code, after a comparison phrase. Used
#: only when the message asks for a comparison and names something the packet
#: does not carry: the answer is then "that was not among the contributors",
#: which is a real answer and not a refusal. Lowercase names are not captured,
#: which is a deliberate limit -- guessing at one would put an entity in the
#: answer that the user never named.
_ENTITY_AFTER_PHRASE = re.compile(
    r"(?:how does|how do|what about|how about|is|are|was|about)\s+"
    r"((?::\d+|[A-Z][\w.'-]*)(?:\s+[A-Z][\w.'-]*)*)"
)


def _spoken_entity(message: str) -> str | None:
    match = _ENTITY_AFTER_PHRASE.search(message)
    if match is None:
        return None
    value = match.group(1).strip()
    # "Is Denver worse" is a name; "Is This" is the sentence restarting.
    return value if value.lower() not in {"i", "it", "this", "that", "the", "there"} else None


def _named_contributor(message: str, insight: dict[str, Any]) -> str | None:
    """A slice value the packet already carries, mentioned in the message.

    Longest first, so "Denver Office" wins over "Denver" when both are ranked.
    Only values that are actually in the packet can match -- the rule router
    never invents an entity name.
    """
    facts = insight.get("chat_facts") or {}
    candidates = [
        str(entry.get("value"))
        for entry in (facts.get("attribution_ranked") or insight.get("attribution") or [])
        if entry.get("value")
    ]
    lowered = message.lower()
    for value in sorted(set(candidates), key=len, reverse=True):
        if len(value) >= 2 and value.lower() in lowered:
            return value
    return None


def classify_by_rules(message: str, insight: dict[str, Any]) -> Route:
    """Deterministic classification. The router of record when the model is off."""
    text = (message or "").strip()
    if not text:
        return Route("OUT_OF_SCOPE", {}, _CONFIDENCE_NONE, "rules", note="empty message")

    lowered = text.lower()
    for pattern, intent_name in _RULES:
        if not re.search(pattern, lowered, re.IGNORECASE):
            continue
        slots: dict[str, Any] = {}
        if intent_name == "CONTROL_CHALLENGE":
            slots["control_name"] = _extract_control_name(lowered)
        elif intent_name == "SHOW_ME_EXAMPLES":
            limit = _extract_limit(lowered)
            if limit is not None:
                slots["limit"] = limit
        elif intent_name == "COMPARE_ENTITY":
            # The packet's own values first; a name the message spells out
            # second. An entity the packet does not carry is still a
            # comparison -- app/chat/templates.py answers it by saying the
            # entity was not among the contributors, which is the honest
            # answer and not the same thing as a refusal.
            entity = _named_contributor(text, insight) or _spoken_entity(text)
            if entity is None:
                continue
            slots["entity_value"] = entity
        return Route(intent_name, slots, _CONFIDENCE_PHRASE, "rules", note=pattern[:40])

    # No phrase matched. A message that names a contributor and nothing else
    # ("what about Denver Office") is still a comparison.
    entity = _named_contributor(text, insight)
    if entity is not None:
        return Route("COMPARE_ENTITY", {"entity_value": entity}, _CONFIDENCE_ENTITY, "rules",
                     note="named contributor")

    return Route("OUT_OF_SCOPE", {}, _CONFIDENCE_NONE, "rules", note="no rule matched")


# --- model router -------------------------------------------------------------

def _prompt(message: str, insight: dict[str, Any], history: list[dict[str, Any]]) -> str:
    payload = {
        "message": message,
        "insight": summarise(insight),
        # Intent labels and nothing else. The previous answers are not re-sent:
        # the router classifies this turn, and a packet per turn is exactly the
        # cost this design exists to avoid.
        "recent_intents": [turn.get("intent") for turn in history if turn.get("intent")][-6:],
    }
    return _PROMPT_PATH.read_text() + "\n\n## Input\n\n" + json.dumps(payload, indent=2, default=str)


def classify_by_model(
    message: str, insight: dict[str, Any], history: list[dict[str, Any]]
) -> Route | None:
    """One model call, or None if it could not be made or could not be parsed."""
    prompt = _prompt(message, insight, history)
    try:
        raw = llm_client.complete(
            system="Respond with strict JSON only, no markdown fences.",
            prompt=prompt,
            max_tokens=MAX_ROUTER_OUTPUT_TOKENS,
            call_type="route_intent",
        )
    except Exception as exc:
        return Route("OUT_OF_SCOPE", {}, 0.0, "model", note=f"model call failed: {exc}")

    parsed = parse_json_object(raw)
    if parsed is None:
        return Route("OUT_OF_SCOPE", {}, 0.0, "model", tokens_in=len(prompt) // 4,
                     tokens_out=len(raw) // 4, note="unparseable router output")

    try:
        confidence = float(parsed.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0

    name = str(parsed.get("intent", "")).strip().upper()
    if name not in intents.BY_NAME:
        return Route("OUT_OF_SCOPE", {}, 0.0, "model", tokens_in=len(prompt) // 4,
                     tokens_out=len(raw) // 4, note=f"unknown intent {name!r}")

    raw_slots = parsed.get("slots")
    return Route(
        name,
        raw_slots if isinstance(raw_slots, dict) else {},
        max(0.0, min(confidence, 1.0)),
        "model",
        tokens_in=len(prompt) // 4,
        tokens_out=len(raw) // 4,
    )


# --- the router ---------------------------------------------------------------

def route(message: str, insight: dict[str, Any], history: list[dict[str, Any]] | None = None) -> Route:
    """Classify one turn, with slots coerced and confidence applied.

    The model runs first when it is enabled. Its answer is taken only if it
    clears MIN_CONFIDENCE; otherwise the rules get a turn, and a confident rule
    match is preferred to a hesitant model one. If neither is confident the
    question is refused -- which is a decision, not a failure.
    """
    history = history or []
    model_route: Route | None = None

    if get_settings().llm_enabled:
        model_route = classify_by_model(message, insight, history)
        if model_route is not None and model_route.confidence >= intents.MIN_CONFIDENCE:
            return _finalise(model_route)

    rules_route = classify_by_rules(message, insight)
    if model_route is not None:
        rules_route.source = "model-then-rules"
        rules_route.tokens_in = model_route.tokens_in
        rules_route.tokens_out = model_route.tokens_out
        rules_route.note = (
            f"model returned {model_route.intent} at {model_route.confidence:.2f} "
            f"(under {intents.MIN_CONFIDENCE}); {rules_route.note}"
        )
    return _finalise(rules_route)


def _finalise(route_: Route) -> Route:
    """Coerce slots through the intent's own declarations and apply the
    confidence floor. Nothing downstream sees a slot this did not vet."""
    if route_.confidence < intents.MIN_CONFIDENCE:
        return Route("OUT_OF_SCOPE", {}, route_.confidence, route_.source,
                     route_.tokens_in, route_.tokens_out,
                     route_.note or "below the confidence floor")
    intent = intents.get(route_.intent)
    route_.intent = intent.name
    route_.slots = intent.fill(route_.slots)
    return route_
