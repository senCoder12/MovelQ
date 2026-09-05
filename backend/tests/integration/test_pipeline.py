from __future__ import annotations

import pytest
from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock
from app.domain.entities import Alert, Trip
from app.domain.enums import AlertScope, SituationType, ActionType
from app.application.services.alert_episode_service import AlertEpisodeService
from app.application.services.signal_service import SignalService
from app.application.services.situation_service import SituationService
from app.application.services.decision_service import DecisionService
from app.application.services.evidence_service import EvidenceService
from app.application.services.agent_service import AgentService
from app.infrastructure.repositories.pg_episode_repository import PgEpisodeRepository
from app.infrastructure.repositories.pg_situation_repository import PgSituationRepository
from app.infrastructure.repositories.pg_decision_repository import PgDecisionRepository


@pytest.mark.asyncio
async def test_alerts_to_episodes_to_situation_to_decision():
    """End-to-End Pipeline:
    Raw Alerts -> Alert Episode -> Signals -> Business Situation -> Evidence -> Decision -> Investigation"""
    # 1. Setup mock repositories
    alert_repo = AsyncMock()
    episode_repo = PgEpisodeRepository()
    situation_repo = PgSituationRepository()
    decision_repo = PgDecisionRepository()

    # 11 raw alerts for Trip 1097076
    base_time = datetime(2026, 7, 15, 12, 3)
    raw_alerts = [
        Alert(
            event_id=f"evt-{i}",
            trip_id=1097076,
            business_unit="catalyst-Slc",
            event_type="VEHICLE_STOPPAGE",
            alert_scope=AlertScope.VEHICLE,
            severity_raw="Sev-2",
            start_ts=base_time + timedelta(minutes=i * 2),
            source="MOBILE",
        )
        for i in range(11)
    ]
    alert_repo.get_alerts_for_trip.return_value = raw_alerts

    trip = Trip(
        trip_id=1097076,
        trip_date=date(2026, 7, 15),
        business_unit="catalyst-Slc",
        office="Oakmont",
        shift="12:00",
        trip_direction="LOGIN",
        delay_minutes=22,
        planned_employee_cnt=8,
        actual_employee_cnt=8,
        noshow_cnt=0,
        is_on_time=False,
    )

    # 2. Episode Service: 11 alerts become 1 episode
    episode_svc = AlertEpisodeService(alert_repo, episode_repo)
    episodes = await episode_svc.build_episodes_for_trip(1097076)
    assert len(episodes) == 1, "11 sequential vehicle stoppage alerts must collapse into 1 episode"
    assert episodes[0].occurrence_count == 11

    # 3. Signal Service
    signal_svc = SignalService()
    signals = signal_svc.detect_signals(trip=trip, episodes=episodes)
    assert len(signals) > 0

    # 4. Situation Service
    situation_svc = SituationService(situation_repository=situation_repo)
    situation = await situation_svc.evaluate_situation(trip=trip, episodes=episodes, signals=signals)
    assert situation is not None
    assert situation.situation_type == SituationType.ROUTE_DISRUPTION
    assert situation.impact.affected_employees == 8
    assert situation.impact.delay_minutes_total == 22

    # 5. Decision Service
    decision_svc = DecisionService(decision_repository=decision_repo)
    decision = await decision_svc.generate_decision(situation)
    assert decision is not None
    assert len(decision.options) >= 3
    assert decision.recommended_action in (ActionType.ESCALATE_VENDOR, ActionType.NOTIFY_EMPLOYEES)

    # 6. Agent Service investigation (uses MockProvider)
    evidence_svc = EvidenceService()
    agent_svc = AgentService(
        evidence_service=evidence_svc,
        situation_repository=situation_repo,
    )
    investigation = await agent_svc.investigate_situation(situation.situation_id)
    assert "summary" in investigation
    assert "why_it_matters" in investigation
    assert "recommended_action" in investigation


@pytest.mark.asyncio
async def test_llm_failure_graceful():
    """INVARIANT 15: The system must remain usable if the LLM is unavailable or throws errors."""
    situation_repo = PgSituationRepository()
    situation = Trip(
        trip_id=999,
        trip_date=date(2026, 7, 15),
        business_unit="catalyst-Slc",
        office="Oakmont",
        shift="03:00",
        delay_minutes=35,
        planned_employee_cnt=5,
    )

    sit_svc = SituationService(situation_repository=situation_repo)
    situation_obj = await sit_svc.evaluate_situation(
        trip=situation,
        episodes=[],
        signals=[],
    )
    # If no episodes/signals, create situation manually
    if not situation_obj:
        from app.domain.entities import Situation, SituationImpact
        situation_obj = Situation(
            situation_id="sit-fallback-test",
            situation_type=SituationType.ROUTE_DISRUPTION,
            business_unit="catalyst-Slc",
            office="Oakmont",
            shift="03:00",
            title="Route Disruption",
            impact=SituationImpact(affected_employees=5, delay_minutes_total=35),
            recommended_actions=["ESCALATE_VENDOR", "NOTIFY_EMPLOYEES"],
        )
        await situation_repo.save_situation(situation_obj)

    # Mock failing LLM provider
    failing_llm = AsyncMock()
    failing_llm.generate.side_effect = RuntimeError("OpenAI API Connection Timeout 504")

    evidence_svc = EvidenceService()
    agent_svc = AgentService(
        evidence_service=evidence_svc,
        situation_repository=situation_repo,
        llm_provider=failing_llm,
    )

    # Must NOT raise unhandled exception, must return deterministic template explanation
    result = await agent_svc.investigate_situation(situation_obj.situation_id)
    assert result is not None
    assert "summary" in result
    assert "mode" in result and result["mode"] == "deterministic_template"
    assert "Oakmont" in result["summary"]
