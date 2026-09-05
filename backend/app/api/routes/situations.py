"""Situation endpoints — the core of MoveIQ.

Situations are living business entities, not raw alerts.
Every situation requires business/operational relevance.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.api.dependencies import (
    get_situation_service,
    get_decision_service,
    get_evidence_service,
    get_agent_service,
    get_employee_repo,
)

router = APIRouter()


@router.get("/situations")
async def get_situations(
    business_unit: str = Query(default="", description="Filter by business unit"),
    status: str = Query(default="", description="Filter by status"),
    limit: int = Query(default=50, ge=1, le=200),
):
    """List active business situations, sorted by priority."""
    situation_svc = get_situation_service()

    situations = await situation_svc.get_active_situations(
        business_unit=business_unit or None,
    )

    if status:
        situations = [s for s in situations if s.status.value == status]

    return [s.model_dump() for s in situations[:limit]]


@router.get("/situations/{situation_id}")
async def get_situation(situation_id: str):
    """Get full situation detail including impact and historical context."""
    situation_svc = get_situation_service()
    situation = await situation_svc.get_situation_detail(situation_id)

    if not situation:
        raise HTTPException(status_code=404, detail="Situation not found")

    # Enrich with LLM investigation if available
    agent_svc = get_agent_service()
    try:
        investigation = await agent_svc.investigate_situation(situation_id)
    except Exception:
        investigation = None

    result = situation.model_dump()
    if investigation:
        result["investigation"] = investigation

    return result


@router.get("/situations/{situation_id}/employees")
async def get_situation_employees(situation_id: str):
    """Get affected employees for a situation."""
    situation_svc = get_situation_service()
    employee_repo = get_employee_repo()

    situation = await situation_svc.get_situation_detail(situation_id)
    if not situation:
        raise HTTPException(status_code=404, detail="Situation not found")

    if not situation.trip_ids:
        return []

    employees = await employee_repo.get_affected_employees(situation.trip_ids)

    # Return aggregated view, not PII
    return [
        {
            "stwid": e.stwid,
            "trip_id": e.trip_id,
            "boarding_status": e.boarding_status,
            "is_no_show": e.is_no_show,
            "pickup_delay_min": e.pickup_delay_min,
            "is_late_pickup": e.is_late_pickup,
            "gender": e.gender,
        }
        for e in employees
    ]


@router.get("/situations/{situation_id}/evidence")
async def get_situation_evidence(situation_id: str):
    """Get structured evidence packet for a situation.

    This is the same evidence sent to the LLM — structured, compact, no PII.
    """
    situation_svc = get_situation_service()
    evidence_svc = get_evidence_service()

    situation = await situation_svc.get_situation_detail(situation_id)
    if not situation:
        raise HTTPException(status_code=404, detail="Situation not found")

    try:
        packet = await evidence_svc.build_evidence_packet(situation)
        return packet.model_dump()
    except Exception as e:
        return {"error": str(e), "situation_id": situation_id}


@router.get("/situations/{situation_id}/decisions")
async def get_situation_decisions(situation_id: str):
    """Get decision comparison for a situation."""
    decision_svc = get_decision_service()
    situation_svc = get_situation_service()

    situation = await situation_svc.get_situation_detail(situation_id)
    if not situation:
        raise HTTPException(status_code=404, detail="Situation not found")

    try:
        decision = await decision_svc.generate_decision(situation)
        return decision.model_dump()
    except Exception as e:
        return {"error": str(e), "situation_id": situation_id}


class ActionRequest(BaseModel):
    action_type: str


@router.post("/situations/{situation_id}/actions")
async def take_action(situation_id: str, request: ActionRequest):
    """Record an action taken on a situation."""
    situation_svc = get_situation_service()
    decision_svc = get_decision_service()

    situation = await situation_svc.get_situation_detail(situation_id)
    if not situation:
        raise HTTPException(status_code=404, detail="Situation not found")

    # Update situation status
    from app.domain.enums import SituationStatus
    from app.core.cache import cache
    await situation_svc.update_situation_status(
        situation_id, SituationStatus.ACTIONED
    )
    cache.delete_pattern("home_dashboard:*")

    return {
        "status": "action_recorded",
        "situation_id": situation_id,
        "action_type": request.action_type,
        "outcome_label": "UNAVAILABLE",
        "message": "Action recorded. Outcome verification will follow when data is available.",
    }
