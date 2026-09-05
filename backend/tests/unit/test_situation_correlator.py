from __future__ import annotations

import pytest
from datetime import date, datetime
from app.domain.entities import Trip, AlertEpisode, Signal, ShiftReadiness
from app.domain.enums import (
    SituationType,
    SituationStatus,
    SituationPriority,
    SignalType,
    EpisodeState,
)
from app.application.services.situation_service import SituationService
from app.infrastructure.repositories.pg_situation_repository import PgSituationRepository


@pytest.mark.asyncio
async def test_episode_no_impact_no_situation():
    """INVARIANT 3 & 4: Episode with no delay, no employee impact -> NO high-priority situation."""
    repo = PgSituationRepository()
    svc = SituationService(situation_repository=repo)

    trip = Trip(
        trip_id=101,
        trip_date=date(2026, 7, 15),
        business_unit="catalyst-Slc",
        office="Oakmont",
        shift="03:00",
        trip_direction="LOGIN",
        delay_minutes=0,
        planned_employee_cnt=4,
        actual_employee_cnt=4,
        noshow_cnt=0,
        is_on_time=True,
    )

    # 11 DEVICE_NOT_REACHABLE alerts -> 1 episode, but trip arrived on time with no delay/safety
    episode = AlertEpisode(
        episode_id="ep-1",
        business_unit="catalyst-Slc",
        trip_id=101,
        event_type="DEVICE_NOT_REACHABLE",
        first_seen=datetime(2026, 7, 15, 2, 10),
        last_seen=datetime(2026, 7, 15, 2, 45),
        occurrence_count=11,
        duration_minutes=35.0,
        state=EpisodeState.ACTIVE,
    )

    situation = await svc.evaluate_situation(trip=trip, episodes=[episode], signals=[])
    assert situation is None, "An alert episode without business impact must NOT become a situation"


@pytest.mark.asyncio
async def test_episode_with_delay_creates_situation():
    """Episode + delay > threshold + employees -> ROUTE_DISRUPTION situation."""
    repo = PgSituationRepository()
    svc = SituationService(situation_repository=repo)

    trip = Trip(
        trip_id=102,
        trip_date=date(2026, 7, 15),
        business_unit="catalyst-Slc",
        office="Oakmont",
        shift="03:00",
        trip_direction="LOGIN",
        delay_minutes=25,
        planned_employee_cnt=6,
        actual_employee_cnt=6,
        noshow_cnt=0,
        is_on_time=False,
    )

    episode = AlertEpisode(
        episode_id="ep-2",
        business_unit="catalyst-Slc",
        trip_id=102,
        event_type="VEHICLE_STOPPAGE",
        first_seen=datetime(2026, 7, 15, 2, 15),
        last_seen=datetime(2026, 7, 15, 2, 35),
        occurrence_count=5,
        duration_minutes=20.0,
        state=EpisodeState.ACTIVE,
    )

    signals = [
        Signal(
            signal_id="sig-1",
            signal_type=SignalType.TRIP_LATE_END,
            business_unit="catalyst-Slc",
            trip_id=102,
            description="Trip arrived 25m late",
            value=25.0,
        )
    ]

    situation = await svc.evaluate_situation(trip=trip, episodes=[episode], signals=signals)
    assert situation is not None
    assert situation.situation_type == SituationType.ROUTE_DISRUPTION
    assert situation.impact.affected_employees == 6
    assert situation.impact.delay_minutes_total == 25


@pytest.mark.asyncio
async def test_situation_deduplication():
    """Same correlation key -> update existing, do NOT create new."""
    repo = PgSituationRepository()
    svc = SituationService(situation_repository=repo)

    trip1 = Trip(
        trip_id=103,
        trip_date=date(2026, 7, 15),
        business_unit="catalyst-Slc",
        office="Oakmont",
        shift="03:00",
        trip_direction="LOGIN",
        delay_minutes=18,
        planned_employee_cnt=4,
    )
    episode1 = AlertEpisode(
        episode_id="ep-10",
        business_unit="catalyst-Slc",
        trip_id=103,
        event_type="VEHICLE_STOPPAGE",
        first_seen=datetime(2026, 7, 15, 2, 0),
        last_seen=datetime(2026, 7, 15, 2, 15),
        occurrence_count=3,
        duration_minutes=15.0,
    )
    sig1 = [
        Signal(
            signal_type=SignalType.TRIP_LATE_END,
            business_unit="catalyst-Slc",
            trip_id=103,
            description="Late",
            value=18.0,
        )
    ]

    sit1 = await svc.evaluate_situation(trip=trip1, episodes=[episode1], signals=sig1)
    assert sit1 is not None
    sit1_id = sit1.situation_id

    # Later new event arrives on same shift/direction
    trip2 = Trip(
        trip_id=104,
        trip_date=date(2026, 7, 15),
        business_unit="catalyst-Slc",
        office="Oakmont",
        shift="03:00",
        trip_direction="LOGIN",
        delay_minutes=24,
        planned_employee_cnt=5,
    )
    sig2 = [
        Signal(
            signal_type=SignalType.TRIP_LATE_END,
            business_unit="catalyst-Slc",
            trip_id=104,
            description="Late",
            value=24.0,
        )
    ]

    sit2 = await svc.evaluate_situation(trip=trip2, episodes=[episode1], signals=sig2)
    assert sit2 is not None
    assert sit2.situation_id == sit1_id, "Must update existing situation instead of creating a duplicate"
    assert 103 in sit2.trip_ids
    assert 104 in sit2.trip_ids


@pytest.mark.asyncio
async def test_readiness_risk_situation():
    """Readiness below threshold -> SHIFT_READINESS_RISK situation."""
    repo = PgSituationRepository()
    svc = SituationService(situation_repository=repo)

    trip = Trip(
        trip_id=105,
        trip_date=date(2026, 7, 15),
        business_unit="catalyst-Slc",
        office="Oakmont",
        shift="03:00",
        trip_direction="LOGIN",
        planned_employee_cnt=10,
    )

    readiness = ShiftReadiness(
        business_unit="catalyst-Slc",
        office="Oakmont",
        shift="03:00",
        direction="LOGIN",
        trip_date=date(2026, 7, 15),
        employees_expected=100,
        employees_ready_on_time=68,
        employees_late=25,
        employees_noshow=7,
        readiness_score=0.68,
        historical_baseline=0.92,
        delta_pp=-24.0,
    )

    signals = [
        Signal(
            signal_type=SignalType.READINESS_BELOW_THRESHOLD,
            business_unit="catalyst-Slc",
            trip_id=105,
            description="Readiness 68% below threshold",
            value=0.68,
        )
    ]

    situation = await svc.evaluate_situation(
        trip=trip, episodes=[], signals=signals, readiness=readiness
    )
    assert situation is not None
    assert situation.situation_type == SituationType.SHIFT_READINESS_RISK
    assert situation.priority in (SituationPriority.HIGH, SituationPriority.CRITICAL)


@pytest.mark.asyncio
async def test_safety_event_creates_situation():
    """Safety event -> SAFETY_SITUATION with CRITICAL priority."""
    repo = PgSituationRepository()
    svc = SituationService(situation_repository=repo)

    trip = Trip(
        trip_id=106,
        trip_date=date(2026, 7, 15),
        business_unit="catalyst-Slc",
        office="Oakmont",
        shift="03:00",
        trip_direction="LOGIN",
        planned_employee_cnt=4,
    )

    signals = [
        Signal(
            signal_type=SignalType.SAFETY_EVENT,
            business_unit="catalyst-Slc",
            trip_id=106,
            description="PANIC_DEVICE triggered",
            value=1.0,
        )
    ]

    situation = await svc.evaluate_situation(trip=trip, episodes=[], signals=signals)
    assert situation is not None
    assert situation.situation_type == SituationType.SAFETY_SITUATION
    assert situation.priority == SituationPriority.CRITICAL
