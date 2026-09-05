"""POST /internal/insight-chat -- one turn of insight-scoped conversation.

Java owns the conversation: it holds the session, caps the history, and writes
every turn to chat_turn including the refusals. This endpoint is a pure
function of (packet, message, recent intent labels) and keeps nothing.

The packet may be posted with the request -- the same object Java rendered on
the card, which is the cheap path and the one the backend takes -- or omitted,
in which case detection is re-run for the tenant and the insight is looked up
by id. Either way the full packet is never re-sent turn after turn: history
carries intent labels and answers only.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from app.chat import intents, service
from app.llm import context

router = APIRouter(prefix="/internal", tags=["internal"])


@router.post("/insight-chat")
def insight_chat(payload: dict[str, Any]) -> dict[str, Any]:
    insight_id = payload.get("insight_id")
    tenant_id = payload.get("tenant_id")
    message = payload.get("message")
    insight = payload.get("insight")

    if not insight_id:
        raise HTTPException(status_code=400, detail="payload.insight_id is required")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="payload.tenant_id is required")
    if not isinstance(message, str) or not message.strip():
        raise HTTPException(status_code=400, detail="payload.message is required")
    if insight is not None and not isinstance(insight, dict):
        raise HTTPException(status_code=400, detail="payload.insight must be an InsightPacket")

    # Bound for the ledger: the router's model call is attributed to this
    # tenant and this insight, or it is refused before it dials out.
    with context.bind(tenant_id=str(tenant_id), insight_id=str(insight_id)):
        try:
            resolved = service.resolve_insight(str(insight_id), str(tenant_id), insight)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"could not resolve insight: {exc}") from exc

        if resolved is None:
            raise HTTPException(status_code=404, detail=f"unknown insight_id: {insight_id}")

        return {
            "insight_id": insight_id,
            **service.answer(resolved, message, payload.get("history")),
        }


@router.post("/insight-chat/starters")
def insight_chat_starters(payload: dict[str, Any]) -> dict[str, Any]:
    """The three opening chips for one insight. Separate from the turn endpoint
    so the drawer can render them before anything has been asked."""
    insight_id = payload.get("insight_id")
    tenant_id = payload.get("tenant_id")
    if not insight_id or not tenant_id:
        raise HTTPException(status_code=400, detail="payload.insight_id and payload.tenant_id are required")

    with context.bind(tenant_id=str(tenant_id), insight_id=str(insight_id)):
        resolved = service.resolve_insight(str(insight_id), str(tenant_id), payload.get("insight"))
    if resolved is None:
        raise HTTPException(status_code=404, detail=f"unknown insight_id: {insight_id}")
    return {
        "insight_id": insight_id,
        "starters": service.starters(resolved),
        "answerable": [
            {"intent": intent.name, "offer": intent.offer} for intent in intents.ANSWERABLE
        ],
    }
