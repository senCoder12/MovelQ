from __future__ import annotations

import pytest
from app.domain.entities import Situation, SituationImpact
from app.domain.enums import SituationType
from app.application.services.evidence_service import EvidenceService


@pytest.fixture
def sample_situation():
    return Situation(
        situation_id="sit-test-100",
        situation_type=SituationType.ROUTE_DISRUPTION,
        business_unit="catalyst-Slc",
        office="Oakmont",
        shift="03:00",
        direction="LOGIN",
        title="Route Disruption on Oakmont 03:00",
        description="Vehicular stoppage causing delay",
        impact=SituationImpact(
            affected_employees=8,
            affected_trips=2,
            affected_routes=1,
            delay_minutes_total=36,
            delay_p95=22.0,
            historical_delay_p95=8.0,
            readiness_delta_pp=-14.5,
        ),
        supporting_episode_ids=["ep-1", "ep-2"],
        recommended_actions=["ESCALATE_VENDOR", "NOTIFY_EMPLOYEES"],
    )


@pytest.mark.asyncio
async def test_no_pii_in_evidence(sample_situation):
    """INVARIANT: Evidence packets sent to the LLM must NEVER contain employee PII
    (no names, phone numbers, email addresses, or precise coordinates)."""
    svc = EvidenceService()
    packet = await svc.build_evidence_packet(sample_situation)
    dump = packet.model_dump()
    raw_str = str(dump).lower()

    forbidden_terms = ["email", "phone", "first_name", "last_name", "home_address", "latitude", "longitude"]
    for term in forbidden_terms:
        assert term not in raw_str, f"PII key '{term}' found in evidence packet"


@pytest.mark.asyncio
async def test_evidence_has_aggregates(sample_situation):
    """Context must favor aggregates, percentiles, and counts over raw trip tables."""
    svc = EvidenceService()
    packet = await svc.build_evidence_packet(sample_situation)

    state = packet.current_state
    assert state["affected_employees"] == 8
    assert state["affected_trips"] == 2
    assert state["delay_minutes_total"] == 36
    assert state["delay_p95_minutes"] == 22.0

    workforce = packet.workforce_impact
    assert workforce["employees_expected"] == 8
    assert workforce["employees_at_risk"] == 8


@pytest.mark.asyncio
async def test_evidence_has_context_version(sample_situation):
    """Every evidence packet must have a deterministic version and evidence hash."""
    svc = EvidenceService()
    packet = await svc.build_evidence_packet(sample_situation)

    assert packet.context_version != ""
    assert packet.evidence_hash != ""
    assert len(packet.evidence_hash) >= 8
