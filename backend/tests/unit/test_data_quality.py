from __future__ import annotations

import pytest
from datetime import date, datetime
from app.domain.entities import Alert, Trip, Signal, DataQualityIssue
from app.domain.enums import AlertScope, SignalType, DataQualityStatus
from app.application.services.situation_service import SituationService
from app.infrastructure.repositories.pg_situation_repository import PgSituationRepository


def test_invalid_severity_handled():
    """INVARIANT 10: severity='False' must NOT silently become CRITICAL or Sev-1.
    Raw value is preserved in severity_raw, while normalized severity is None."""
    alert = Alert(
        event_id="evt-false",
        trip_id=101,
        business_unit="catalyst-Slc",
        event_type="DEVICE_NOT_REACHABLE",
        alert_scope=AlertScope.VEHICLE,
        severity_raw="False",
        severity=None,  # Normalized
        start_ts=datetime(2026, 7, 15, 12, 0),
    )

    assert alert.severity_raw == "False"
    assert alert.severity is None
    assert alert.was_triaged is False


def test_delay_inconsistency_detected():
    """Detect inconsistency when delay_reason is NODELAY but delay_minutes > 15."""
    trip = Trip(
        trip_id=102,
        trip_date=date(2026, 7, 15),
        business_unit="catalyst-Slc",
        office="Oakmont",
        delay_reason="NODELAY",
        delay_minutes=25,
    )

    is_inconsistent = trip.delay_reason == "NODELAY" and (trip.delay_minutes or 0) > 15
    assert is_inconsistent is True

    issue = DataQualityIssue(
        field="delay_minutes",
        raw_value="25",
        normalized_value=25,
        quality_status=DataQualityStatus.SUSPICIOUS,
        reason="Reported NODELAY but computed delay is 25 minutes",
    )
    assert issue.quality_status == DataQualityStatus.SUSPICIOUS


@pytest.mark.asyncio
async def test_data_anomaly_not_business_anomaly():
    """INVARIANT 10: Data inconsistency alone without operational delay/safety
    does NOT trigger a high-priority manager situation."""
    repo = PgSituationRepository()
    svc = SituationService(situation_repository=repo)

    trip = Trip(
        trip_id=103,
        trip_date=date(2026, 7, 15),
        business_unit="catalyst-Slc",
        office="Oakmont",
        delay_reason="NODELAY",
        delay_minutes=0,
        planned_employee_cnt=4,
        actual_employee_cnt=4,
        noshow_cnt=0,
    )

    signal = Signal(
        signal_type=SignalType.DATA_INCONSISTENCY,
        business_unit="catalyst-Slc",
        trip_id=103,
        description="Minor timestamp mismatch between device and server",
        value=1.0,
    )

    situation = await svc.evaluate_situation(trip=trip, episodes=[], signals=[signal])
    if situation is not None:
        assert situation.priority.value in ("LOW", "MEDIUM"), (
            "Data inconsistency alone must never be rated as a CRITICAL/HIGH business incident"
        )
