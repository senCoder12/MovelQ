"""POST /internal/draft-action -- draft one action from an InsightPacket.

Java has already fetched the full InsightPacket (same object it renders on
the card) and posts it back here alongside the action `type` it wants
drafted -- the agent never looks an insight up by id itself, so it stays a
pure function of the packet it is given, same shape as
POST /internal/leadership-narrative.

The agent never executes: this endpoint's only output is a draft (subject,
body, facts_cited, preview) for Java to persist as DRAFTED and a human to
approve or reject. See app/actions/drafters.py for the LLM/validate/retry/
fallback pipeline behind `subject`/`body`; everything else in the response
is computed deterministically from fields already on the insight.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from app.actions import drafters
from app.llm import context

router = APIRouter(prefix="/internal", tags=["internal"])


@router.post("/draft-action")
def draft_action(payload: dict[str, Any]) -> dict[str, Any]:
    insight = payload.get("insight")
    action_type = payload.get("type")
    if not isinstance(insight, dict) or not insight.get("insight_id"):
        raise HTTPException(status_code=400, detail="payload.insight must be an InsightPacket")
    if not action_type:
        raise HTTPException(status_code=400, detail="payload.type is required")

    # The tenant is already bound by the middleware; the insight is only known
    # here, and binding it is what lets the cost query answer "cost per insight".
    with context.bind(insight_id=insight["insight_id"]):
        try:
            return drafters.draft_action(insight, action_type)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
