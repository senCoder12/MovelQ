from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

import structlog

from app.config import get_settings
from app.domain.entities import AlertEpisode, HistoricalBaseline, ShiftReadiness, Signal, Trip
from app.domain.enums import EvidenceType, SignalType

logger = structlog.get_logger(__name__)


class SignalService:
    """Deterministic signal detection engine.

    Evaluates trips, alert episodes, and historical baselines to produce
    meaningful operational observations (Signals).
    """

    def __init__(self):
        self.settings = get_settings()

    def detect_signals(
        self,
        trip: Trip,
        episodes: List[AlertEpisode],
        baseline: Optional[HistoricalBaseline] = None,
        readiness: Optional[ShiftReadiness] = None,
    ) -> List[Signal]:
        signals: List[Signal] = []
        sla = float(self.settings.sla_on_time_minutes)

        bu = trip.business_unit
        trip_id = trip.trip_id
        office = trip.office
        shift = trip.shift
        direction = trip.trip_direction

        # 1. TRIP_LATE_START
        if trip.actual_start_ts and trip.planned_start_ts:
            start_delay = (trip.actual_start_ts - trip.planned_start_ts).total_seconds() / 60.0
            if start_delay > sla:
                signals.append(
                    Signal(
                        signal_id=str(uuid.uuid4()),
                        signal_type=SignalType.TRIP_LATE_START,
                        business_unit=bu,
                        trip_id=trip_id,
                        office=office,
                        shift=shift,
                        direction=direction,
                        description=f"Trip started {start_delay:.1f} minutes behind planned schedule",
                        value=round(start_delay, 1),
                        threshold=sla,
                        evidence_type=EvidenceType.OBSERVED_FACT,
                    )
                )

        # 2. TRIP_LATE_END
        delay_mins = float(trip.delay_minutes or 0)
        if not delay_mins and trip.actual_end_ts and trip.planned_end_ts:
            delay_mins = (trip.actual_end_ts - trip.planned_end_ts).total_seconds() / 60.0

        if delay_mins > sla:
            signals.append(
                Signal(
                    signal_id=str(uuid.uuid4()),
                    signal_type=SignalType.TRIP_LATE_END,
                    business_unit=bu,
                    trip_id=trip_id,
                    office=office,
                    shift=shift,
                    direction=direction,
                    description=f"Trip arrival delay is {delay_mins:.1f} minutes (SLA: {sla}m)",
                    value=round(delay_mins, 1),
                    threshold=sla,
                    evidence_type=EvidenceType.OBSERVED_FACT,
                )
            )

        # 3. DELAY_ABOVE_BASELINE
        if baseline and baseline.p90 and delay_mins > baseline.p90:
            signals.append(
                Signal(
                    signal_id=str(uuid.uuid4()),
                    signal_type=SignalType.DELAY_ABOVE_BASELINE,
                    business_unit=bu,
                    trip_id=trip_id,
                    office=office,
                    shift=shift,
                    direction=direction,
                    description=f"Delay of {delay_mins:.1f}m exceeds historical p90 baseline ({baseline.p90:.1f}m)",
                    value=round(delay_mins, 1),
                    baseline_value=baseline.p90,
                    threshold=baseline.p90,
                    evidence_type=EvidenceType.HISTORICAL_EVIDENCE,
                )
            )

        # 4. NOSHOW_RATE_ELEVATED
        noshow = trip.noshow_cnt or 0
        planned = trip.planned_employee_cnt or 0
        if planned > 0:
            noshow_rate = noshow / planned
            if noshow_rate > 0.20:
                signals.append(
                    Signal(
                        signal_id=str(uuid.uuid4()),
                        signal_type=SignalType.NOSHOW_RATE_ELEVATED,
                        business_unit=bu,
                        trip_id=trip_id,
                        office=office,
                        shift=shift,
                        direction=direction,
                        description=f"Employee no-show rate elevated at {noshow_rate:.1%} ({noshow}/{planned})",
                        value=round(noshow_rate, 3),
                        threshold=0.20,
                        evidence_type=EvidenceType.OBSERVED_FACT,
                    )
                )

        # 5. ALERT_EPISODE_PERSISTENT & SAFETY_EVENT
        safety_events = {"PANIC_DEVICE", "OVER_SPEEDING", "PANIC_FIXED_DEVICE"}
        for ep in episodes:
            if ep.duration_minutes > 30.0:
                signals.append(
                    Signal(
                        signal_id=str(uuid.uuid4()),
                        signal_type=SignalType.ALERT_EPISODE_PERSISTENT,
                        business_unit=bu,
                        trip_id=trip_id,
                        office=office,
                        shift=shift,
                        direction=direction,
                        description=f"Alert episode for {ep.event_type} has persisted for {ep.duration_minutes:.0f}m ({ep.occurrence_count} occurrences)",
                        value=ep.duration_minutes,
                        threshold=30.0,
                        evidence_type=EvidenceType.OBSERVED_FACT,
                    )
                )

            if ep.event_type in safety_events:
                signals.append(
                    Signal(
                        signal_id=str(uuid.uuid4()),
                        signal_type=SignalType.SAFETY_EVENT,
                        business_unit=bu,
                        trip_id=trip_id,
                        office=office,
                        shift=shift,
                        direction=direction,
                        description=f"Safety event episode detected: {ep.event_type} ({ep.occurrence_count} occurrences)",
                        value=float(ep.occurrence_count),
                        evidence_type=EvidenceType.OBSERVED_FACT,
                    )
                )

        # 6. READINESS_BELOW_THRESHOLD
        if readiness and readiness.readiness_score < self.settings.readiness_threshold_warning:
            signals.append(
                Signal(
                    signal_id=str(uuid.uuid4()),
                    signal_type=SignalType.READINESS_BELOW_THRESHOLD,
                    business_unit=bu,
                    trip_id=trip_id,
                    office=office,
                    shift=shift,
                    direction=direction,
                    description=f"Shift readiness {readiness.readiness_score:.1%} is below operational warning threshold ({self.settings.readiness_threshold_warning:.0%})",
                    value=round(readiness.readiness_score, 3),
                    threshold=self.settings.readiness_threshold_warning,
                    baseline_value=readiness.historical_baseline,
                    evidence_type=EvidenceType.OBSERVED_FACT,
                )
            )

        return signals
