"""Ask Move — conversational intelligence endpoint.

Flow: User question → Intent detection → Relevant domain tool → Structured evidence → LLM response.
The LLM does NOT freely invent SQL. Explicit backend tools/functions are used.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.dependencies import get_agent_service

router = APIRouter()


class AskRequest(BaseModel):
    question: str
    context: Optional[Dict[str, Any]] = None


@router.post("/ask")
async def ask_move(request: AskRequest):
    """Ask Move a question about mobility operations.

    Examples:
    - "Which shifts are at risk today?"
    - "Why is the 3 AM Oakmont shift at risk?"
    - "Which employees are affected?"
    - "Is this worse than normal?"
    - "Which vendor is contributing to the issue?"
    - "What happens if I do nothing?"
    """
    agent_svc = get_agent_service()

    try:
        result = await agent_svc.ask_move(
            question=request.question,
            context=request.context or {},
        )
        return result
    except Exception as e:
        # Graceful degradation — never let LLM failure break the system
        return {
            "answer": (
                "I'm unable to provide a detailed analysis right now, "
                "but the deterministic situation data is still available "
                "in the Situations and Readiness views."
            ),
            "evidence": {},
            "confidence": "LOW",
            "error": str(e),
        }
