"""Decision endpoints."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Query

from app.api.dependencies import get_decision_service, get_situation_service

router = APIRouter()


@router.get("/decisions")
async def get_decisions(
    business_unit: str = Query(default="", description="Filter by business unit"),
):
    """Get all active decisions for current situations."""
    situation_svc = get_situation_service()
    decision_svc = get_decision_service()

    situations = await situation_svc.get_active_situations(
        business_unit=business_unit or None
    )

    # generate_decision is timeout-guarded per call (see DecisionService's
    # _LLM_TIMEOUT_SECONDS), but run one situation at a time that still adds
    # up to N * timeout in the worst case. Fan them out concurrently instead
    # so the whole page waits on the single slowest call, not the sum of all.
    async def _build(situation):
        try:
            decision = await decision_svc.generate_decision(situation)
            return {
                "situation": situation.model_dump(),
                "decision": decision.model_dump(),
            }
        except Exception:
            return None

    results = await asyncio.gather(*(_build(s) for s in situations))
    return [r for r in results if r is not None]
