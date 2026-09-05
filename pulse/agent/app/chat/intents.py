"""The eight questions this system can answer, and the ninth that says no.

Every intent declares three things, and all three are load-bearing:

  * ``slots`` -- what the router is allowed to extract, with the coercion and
    bounds applied here rather than trusted from the model. A slot value that
    does not coerce is dropped, not guessed at.
  * ``reads`` -- which packet fields the answer is assembled from. This is the
    contract the templates keep and the eval checks: an answer may cite a
    number only if it appears in one of these fields.
  * ``examples`` -- 2-3 phrasings, used both in the router prompt and by the
    offline rule router (app/chat/router.py).

The list is closed on purpose. A question that is not one of these gets
OUT_OF_SCOPE, which names what *can* be asked and attempts nothing else -- a
confident wrong answer costs more than a refusal.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

# --- slots -------------------------------------------------------------------

#: Control dimensions a challenge can name. These are aliases the *user* uses;
#: app/chat/facts.py maps them onto whichever slice column the metric actually
#: declares (vendor -> vendor_id or vendor, hour -> shift_bucket, ...).
CONTROL_NAMES = ("vendor", "hour", "office", "other")

EXAMPLES_DEFAULT_LIMIT = 10
EXAMPLES_MAX_LIMIT = 25


def _coerce_control_name(raw: Any) -> str | None:
    if not isinstance(raw, str):
        return None
    value = raw.strip().lower()
    if value in CONTROL_NAMES:
        return value
    # The router is told to emit one of four names; anything else it invents
    # is a control we did not test, which is exactly what "other" means.
    return "other" if value else None


def _coerce_limit(raw: Any) -> int | None:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return max(1, min(value, EXAMPLES_MAX_LIMIT))


def _coerce_entity_value(raw: Any) -> str | None:
    if not isinstance(raw, str):
        return None
    value = raw.strip()
    return value or None


@dataclass(frozen=True)
class Slot:
    name: str
    description: str
    coerce: Callable[[Any], Any]
    default: Any = None
    required: bool = True


@dataclass(frozen=True)
class Intent:
    name: str
    #: One line, shown to the router and to the user in the refusal message.
    question: str
    reads: tuple[str, ...]
    examples: tuple[str, ...] = ()
    slots: tuple[Slot, ...] = ()
    #: Prose for the OUT_OF_SCOPE message. Phrased as the user would ask it.
    offer: str = ""

    def fill(self, raw_slots: dict[str, Any] | None) -> dict[str, Any]:
        """Coerce what the router produced into what the template will read.

        Unknown keys are dropped, bad values fall back to the declared default,
        and a required slot with no usable value is simply absent -- templates
        are written to handle that rather than to trust the router.
        """
        raw = raw_slots or {}
        filled: dict[str, Any] = {}
        for slot in self.slots:
            value = slot.coerce(raw.get(slot.name)) if slot.name in raw else None
            if value is None:
                value = slot.default
            if value is not None:
                filled[slot.name] = value
        return filled


WHY_THIS_DIMENSION = Intent(
    name="WHY_THIS_DIMENSION",
    question="Why is this attributed to that dimension and not another one?",
    reads=("attribution", "chat_facts.attribution_ranked", "controls", "chat_facts.controls_detail"),
    examples=(
        "why the :16 codes and not the vendor?",
        "how did you decide it's the office and not the shift type?",
        "why is this the dimension that matters",
    ),
    offer="why the finding is attributed to one dimension rather than another",
)

IS_SAMPLE_SUFFICIENT = Intent(
    name="IS_SAMPLE_SUFFICIENT",
    question="Is the sample large enough for this to be real?",
    reads=("metric.n", "chat_facts.sample"),
    examples=(
        "is 29,854 trips enough?",
        "is the sample size big enough to trust this",
        "could this just be noise",
    ),
    offer="whether the sample is large enough, and how far past baseline the deviation is",
)

CONTROL_CHALLENGE = Intent(
    name="CONTROL_CHALLENGE",
    question="Couldn't this be explained by some other factor?",
    reads=("controls", "chat_facts.controls_detail"),
    slots=(
        Slot(
            name="control_name",
            description=f"one of {', '.join(CONTROL_NAMES)}",
            coerce=_coerce_control_name,
            default="other",
        ),
    ),
    examples=(
        "couldn't this just be the vendor?",
        "isn't this just evening trips?",
        "this is probably just one office right",
    ),
    offer="whether a confound (vendor, time of day, office) explains the gap away",
)

WHAT_IF_DATA_WRONG = Intent(
    name="WHAT_IF_DATA_WRONG",
    question="What happens to this if the excluded or bad rows are wrong?",
    reads=("data_quality", "chat_facts.exclusions"),
    examples=(
        "what if the excluded rows change this?",
        "how much data did you throw away",
        "what if the underlying data is wrong",
    ),
    offer="what the excluded rows could do to the number, best and worst case",
)

WHEN_DID_IT_START = Intent(
    name="WHEN_DID_IT_START",
    question="When did this start?",
    reads=("chat_facts.timeline", "coincident_events", "metric.window"),
    examples=(
        "when did this begin?",
        "how long has this been going on",
        "did something change in July",
    ),
    offer="when the pattern started, or why no start date is inferable",
)

SHOW_ME_EXAMPLES = Intent(
    name="SHOW_ME_EXAMPLES",
    question="Show me some of the underlying rows.",
    reads=("chat_facts.examples",),
    slots=(
        Slot(
            name="limit",
            description=f"how many rows, default {EXAMPLES_DEFAULT_LIMIT}, max {EXAMPLES_MAX_LIMIT}",
            coerce=_coerce_limit,
            default=EXAMPLES_DEFAULT_LIMIT,
        ),
    ),
    examples=(
        "show me some of these trips",
        "can I see 20 examples",
        "give me the actual rows",
    ),
    offer="a sample of the underlying trips behind the finding",
)

COMPARE_ENTITY = Intent(
    name="COMPARE_ENTITY",
    question="How does one named entity compare to the others?",
    reads=("attribution", "chat_facts.attribution_ranked"),
    slots=(
        Slot(
            name="entity_value",
            description="the vendor / office / code the question names, copied verbatim",
            coerce=_coerce_entity_value,
        ),
    ),
    examples=(
        "how does Vikram compare to the others?",
        "what about Denver Office",
        "is VND-2 worse than the rest",
    ),
    offer="how one named vendor, office or code compares to the other contributors",
)

WHAT_SHOULD_I_DO = Intent(
    name="WHAT_SHOULD_I_DO",
    question="What do you recommend?",
    reads=("narrative.recommended_actions", "chat_facts.action_drafts"),
    examples=(
        "what do you recommend?",
        "what should I do about this",
        "what's the next step here",
    ),
    offer="what the recommended next action is, and what has already been drafted",
)

OUT_OF_SCOPE = Intent(
    name="OUT_OF_SCOPE",
    question="Anything this system cannot answer from this insight.",
    reads=(),
    examples=(
        "what's the weather",
        "summarise all our vendors",
        "write me a SQL query for last quarter",
    ),
)

#: The eight answerable intents, in the order the refusal message lists them.
ANSWERABLE: tuple[Intent, ...] = (
    WHY_THIS_DIMENSION,
    IS_SAMPLE_SUFFICIENT,
    CONTROL_CHALLENGE,
    WHAT_IF_DATA_WRONG,
    WHEN_DID_IT_START,
    SHOW_ME_EXAMPLES,
    COMPARE_ENTITY,
    WHAT_SHOULD_I_DO,
)

ALL: tuple[Intent, ...] = ANSWERABLE + (OUT_OF_SCOPE,)

BY_NAME: dict[str, Intent] = {intent.name: intent for intent in ALL}

#: Below this the router's answer is not trusted and the question is refused.
#: Deliberately high: an unrecognised question costs a refusal, a misrouted one
#: costs a confident wrong answer.
MIN_CONFIDENCE = 0.6


def get(name: str | None) -> Intent:
    """The named intent, or OUT_OF_SCOPE. Never raises -- an unknown label from
    the router is a refusal, not a 500."""
    return BY_NAME.get((name or "").strip().upper(), OUT_OF_SCOPE)


def refusal_message() -> str:
    """The fixed OUT_OF_SCOPE answer: what this cannot do, then what it can."""
    offers = "\n".join(f"- {intent.offer}" for intent in ANSWERABLE)
    return (
        "I can't answer that from this insight. I only answer questions about "
        "this one finding, using figures that were already computed for it -- I "
        "can't query the warehouse freely, compare across insights, or answer "
        "from general knowledge.\n\n"
        "What I can answer here:\n" + offers
    )
