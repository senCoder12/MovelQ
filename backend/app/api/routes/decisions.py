"""Decision endpoints."""

from __future__ import annotations

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

    decisions = []
    for situation in situations:
        try:
            decision = await decision_svc.generate_decision(situation)
            decisions.append({
                "situation": situation.model_dump(),
                "decision": decision.model_dump(),
            })
        except Exception:
            continue

    return decisions
