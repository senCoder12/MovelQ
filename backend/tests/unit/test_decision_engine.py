from __future__ import annotations

import pytest
from app.domain.entities import Situation, SituationImpact
from app.domain.enums import SituationType, ActionType, EvidenceType
from app.application.services.decision_service import DecisionService
from app.infrastructure.repositories.pg_decision_repository import PgDecisionRepository


@pytest.fixture
def decision_service():
    repo = PgDecisionRepository()
    return DecisionService(decision_repository=repo)


@pytest.mark.asyncio
async def test_do_nothing_always_present(decision_service):
    """INVARIANT: Every decision comparison must include DO_NOTHING as baseline."""
    situation = Situation(
        situation_id="sit-1",
        situation_type=SituationType.ROUTE_DISRUPTION,
        business_unit="catalyst-Slc",
        title="Route Disruption",
        impact=SituationImpact(affected_employees=8, delay_minutes_total=25),
    )
    decision = await decision_service.generate_decision(situation)

    action_types = [opt.action_type for opt in decision.options]
    assert ActionType.DO_NOTHING in action_types


@pytest.mark.asyncio
async def test_vendor_escalation_for_vendor_issue(decision_service):
    """VENDOR_RELIABILITY -> includes ESCALATE_VENDOR option."""
    situation = Situation(
        situation_id="sit-2",
        situation_type=SituationType.VENDOR_RELIABILITY,
        business_unit="catalyst-Slc",
        title="Vendor Lateness",
        impact=SituationImpact(affected_employees=12, delay_minutes_total=40),
    )
    decision = await decision_service.generate_decision(situation)

    action_types = [opt.action_type for opt in decision.options]
    assert ActionType.ESCALATE_VENDOR in action_types


@pytest.mark.asyncio
async def test_notify_for_employee_impact(decision_service):
    """Situation with affected employees -> includes NOTIFY_EMPLOYEES."""
    situation = Situation(
        situation_id="sit-3",
        situation_type=SituationType.SHIFT_READINESS_RISK,
        business_unit="catalyst-Slc",
        title="Readiness Drop",
        impact=SituationImpact(affected_employees=20, readiness_delta_pp=-15.0),
    )
    decision = await decision_service.generate_decision(situation)

    action_types = [opt.action_type for opt in decision.options]
    assert ActionType.NOTIFY_EMPLOYEES in action_types


@pytest.mark.asyncio
async def test_confidence_labels(decision_service):
    """Every option must have explicit confidence and evidence_type."""
    situation = Situation(
        situation_id="sit-4",
        situation_type=SituationType.ROUTE_DISRUPTION,
        business_unit="catalyst-Slc",
        title="Route Disruption",
        impact=SituationImpact(affected_employees=6, delay_minutes_total=18),
    )
    decision = await decision_service.generate_decision(situation)

    for opt in decision.options:
        assert opt.confidence in ("HIGH", "MEDIUM", "LOW")
        assert isinstance(opt.evidence_type, EvidenceType)
        assert len(opt.supporting_evidence) > 0


@pytest.mark.asyncio
async def test_what_if_labeled_as_estimate(decision_service):
    """INVARIANT 9: Any simulated outcome must be labeled as ESTIMATED_SCENARIO or HISTORICAL_EVIDENCE."""
    situation = Situation(
        situation_id="sit-5",
        situation_type=SituationType.ROUTE_DISRUPTION,
        business_unit="catalyst-Slc",
        title="Route Disruption",
        impact=SituationImpact(affected_employees=10, delay_minutes_total=30),
    )
    decision = await decision_service.generate_decision(situation)

    reassign_opt = next(
        (opt for opt in decision.options if opt.action_type == ActionType.SIMULATE_VEHICLE_REASSIGNMENT),
        None,
    )
    assert reassign_opt is not None
    assert reassign_opt.evidence_type == EvidenceType.ESTIMATED_SCENARIO, (
        "Vehicle reassignment simulation must be explicitly labeled as ESTIMATED_SCENARIO, never a guarantee"
    )
