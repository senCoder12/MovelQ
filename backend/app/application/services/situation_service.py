from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

import structlog

from app.config import get_settings
from app.domain.entities import (
    AlertEpisode,
    HistoricalBaseline,
    ShiftReadiness,
    Signal,
    Situation,
    SituationImpact,
    Trip,
)
from app.domain.enums import (
    SignalType,
    SituationPriority,
    SituationStatus,
    SituationType,
)
from app.domain.interfaces import (
    AlertEpisodeRepository,
    EmployeeRepository,
    SituationRepository,
    TripRepository,
)

logger = structlog.get_logger(__name__)


class SituationService:
    """Core situation intelligence engine.

    Correlates signals and alert episodes into meaningful business situations.
    Enforces deduplication, lifecycle management, and priority assignment.
    """

    def __init__(
        self,
        situation_repository: SituationRepository,
        episode_repository: Optional[AlertEpisodeRepository] = None,
        trip_repository: Optional[TripRepository] = None,
        employee_repository: Optional[EmployeeRepository] = None,
        signal_service: Optional[Any] = None,
        impact_service: Optional[Any] = None,
    ):
        self.situation_repository = situation_repository
        self.episode_repository = episode_repository
        self.trip_repository = trip_repository
        self.employee_repository = employee_repository
        self.signal_service = signal_service
        self.impact_service = impact_service
        self.settings = get_settings()

    async def evaluate_situation(
        self,
        trip: Trip,
        episodes: List[AlertEpisode],
        signals: List[Signal],
        baseline: Optional[HistoricalBaseline] = None,
        readiness: Optional[ShiftReadiness] = None,
    ) -> Optional[Situation]:
        """Evaluate whether signals and episodes constitute a business situation.

        INVARIANT 3: An Alert Episode does NOT automatically become a situation.
        INVARIANT 4: A Situation must have business/operational relevance.
        """
        logger.info("situation.evaluate", trip_id=trip.trip_id)

        has_delay = any(
            s.signal_type in (SignalType.TRIP_LATE_START, SignalType.TRIP_LATE_END, SignalType.DELAY_ABOVE_BASELINE)
            for s in signals
        )
        has_employee_impact = (
            any(s.signal_type == SignalType.NOSHOW_RATE_ELEVATED for s in signals)
            or (trip.noshow_cnt or 0) > 0
            or (trip.planned_employee_cnt or 0) > 0 and has_delay
        )
        has_safety_concern = any(s.signal_type == SignalType.SAFETY_EVENT for s in signals)
        has_readiness_risk = any(s.signal_type == SignalType.READINESS_BELOW_THRESHOLD for s in signals)

        # If only device alerts occurred without delay, employee impact, or safety: DO NOT CREATE SITUATION
        if episodes and not has_delay and not has_safety_concern and not has_readiness_risk and (trip.delay_minutes or 0) <= 0:
            logger.info("situation.skipped_no_operational_impact", trip_id=trip.trip_id)
            return None

        if not signals and not episodes:
            return None

        # Determine Situation Type
        sit_type: Optional[SituationType] = None
        title = ""
        description = ""

        if has_safety_concern:
            sit_type = SituationType.SAFETY_SITUATION
            title = f"Safety incident reported on Trip {trip.trip_id}"
            description = "Safety-related alert episode detected during active transit."
        elif has_delay and any(ep.event_type in ("VEHICLE_STOPPAGE", "DEVICE_NOT_REACHABLE") for ep in episodes):
            sit_type = SituationType.ROUTE_DISRUPTION
            delay_val = trip.delay_minutes or 0
            title = f"Route disruption on Trip {trip.trip_id} ({delay_val}m delay)"
            description = f"Vehicle stoppage and persistent alerts contributing to downstream trip delay."
        elif has_readiness_risk:
            sit_type = SituationType.SHIFT_READINESS_RISK
            delta_str = f" ({readiness.delta_pp:+.1f}pp)" if readiness and readiness.delta_pp is not None else ""
            title = f"Shift Readiness Risk at {trip.office or 'Office'} ({trip.shift or 'Shift'})"
            description = f"Current readiness below operational threshold{delta_str}."
        elif any(s.signal_type == SignalType.VENDOR_PERFORMANCE_DEGRADED for s in signals):
            sit_type = SituationType.VENDOR_RELIABILITY
            title = f"Vendor reliability degradation: {trip.vendor or 'Unknown vendor'}"
            description = "Recurring performance delays detected across vendor fleet."
        elif has_employee_impact and has_delay:
            sit_type = SituationType.EMPLOYEE_IMPACT_CLUSTER
            emp_cnt = trip.planned_employee_cnt or 0
            title = f"Employee impact cluster: {emp_cnt} riders affected on Trip {trip.trip_id}"
            description = "Elevated employee lateness and risk to arrival readiness."
        elif any(s.signal_type == SignalType.DATA_INCONSISTENCY for s in signals):
            sit_type = SituationType.DATA_CONFIDENCE
            title = f"Data confidence issue on Trip {trip.trip_id}"
            description = "Discrepancy detected between recorded delay and GPS tracking timestamps."

        if not sit_type:
            return None

        # Compute priority
        priority = self._calculate_priority(sit_type, trip, signals, readiness)

        # Build situation correlation key
        if sit_type in (SituationType.ROUTE_DISRUPTION, SituationType.SAFETY_SITUATION):
            corr_key = f"{trip.business_unit}|{trip.office or ''}|{trip.shift or ''}|{trip.trip_id}|{sit_type.value}"
        else:
            corr_key = f"{trip.business_unit}|{trip.office or ''}|{trip.shift or ''}|{trip.trip_direction or ''}|{sit_type.value}"

        # Deduplication / Update existing situation
        existing = await self.situation_repository.find_by_correlation_key(corr_key)

        now = datetime.utcnow()
        supporting_signal_ids = [s.signal_id for s in signals]
        supporting_episode_ids = [ep.episode_id for ep in episodes]

        # Calculate impact
        impact = SituationImpact(
            affected_employees=trip.planned_employee_cnt or 0,
            affected_trips=1,
            affected_routes=1,
            delay_minutes_total=trip.delay_minutes or 0,
            delay_p95=float(trip.delay_minutes or 0),
            historical_delay_p95=baseline.p90 if baseline else None,
            readiness_delta_pp=readiness.delta_pp if readiness else None,
            noshow_count=trip.noshow_cnt or 0,
        )

        # Recommended actions depending on situation type
        recommended_actions = self._get_recommended_actions(sit_type)

        if existing:
            # Update existing situation in-place rather than creating duplicate
            existing.priority = priority
            existing.last_seen = now
            existing.updated_at = now
            if trip.trip_id not in existing.trip_ids:
                existing.trip_ids.append(trip.trip_id)
            existing.supporting_signal_ids = list(set(existing.supporting_signal_ids + supporting_signal_ids))
            existing.supporting_episode_ids = list(set(existing.supporting_episode_ids + supporting_episode_ids))
            existing.impact.affected_trips = len(existing.trip_ids)
            existing.impact.affected_employees = max(existing.impact.affected_employees, impact.affected_employees)
            existing.impact.delay_minutes_total += impact.delay_minutes_total
            await self.situation_repository.update_situation(existing)
            logger.info("situation.updated_existing", situation_id=existing.situation_id)
            return existing

        # Create new Situation
        new_sit = Situation(
            situation_id=str(uuid.uuid4()),
            situation_type=sit_type,
            status=SituationStatus.DETECTED,
            priority=priority,
            title=title,
            description=description,
            business_unit=trip.business_unit,
            office=trip.office,
            shift=trip.shift,
            direction=trip.trip_direction,
            trip_ids=[trip.trip_id],
            route_ids=[trip.route_source] if trip.route_source else [],
            impact=impact,
            supporting_signal_ids=supporting_signal_ids,
            supporting_episode_ids=supporting_episode_ids,
            historical_context={"baseline_p90": baseline.p90 if baseline else None},
            confidence=0.95,
            recommended_actions=recommended_actions,
            first_seen=now,
            last_seen=now,
            created_at=now,
            updated_at=now,
        )

        await self.situation_repository.save_situation(new_sit)
        logger.info("situation.created_new", situation_id=new_sit.situation_id, type=sit_type.value)
        return new_sit

    def _calculate_priority(
        self,
        sit_type: SituationType,
        trip: Trip,
        signals: List[Signal],
        readiness: Optional[ShiftReadiness] = None,
    ) -> SituationPriority:
        if sit_type == SituationType.SAFETY_SITUATION:
            return SituationPriority.CRITICAL

        delay = trip.delay_minutes or 0
        if delay >= 30:
            return SituationPriority.CRITICAL

        if sit_type == SituationType.SHIFT_READINESS_RISK:
            if readiness and readiness.readiness_score < 0.70:
                return SituationPriority.CRITICAL
            return SituationPriority.HIGH

        if (trip.planned_employee_cnt or 0) >= 4 and delay >= 15:
            return SituationPriority.HIGH

        if delay >= 15 or (trip.noshow_cnt or 0) >= 2:
            return SituationPriority.MEDIUM

        return SituationPriority.LOW

    def _get_recommended_actions(self, sit_type: SituationType) -> List[str]:
        if sit_type == SituationType.SHIFT_READINESS_RISK:
            return ["NOTIFY_EMPLOYEES", "ESCALATE_VENDOR", "DO_NOTHING"]
        elif sit_type == SituationType.ROUTE_DISRUPTION:
            return ["SIMULATE_VEHICLE_REASSIGNMENT", "NOTIFY_EMPLOYEES", "ESCALATE_VENDOR", "DO_NOTHING"]
        elif sit_type == SituationType.VENDOR_RELIABILITY:
            return ["ESCALATE_VENDOR", "NOTIFY_EMPLOYEES", "DO_NOTHING"]
        elif sit_type == SituationType.SAFETY_SITUATION:
            return ["NOTIFY_EMPLOYEES", "ESCALATE_VENDOR"]
        return ["NOTIFY_EMPLOYEES", "DO_NOTHING"]

    async def get_active_situations(
        self, business_unit: Optional[str] = None
    ) -> List[Situation]:
        return await self.situation_repository.get_situations(
            business_unit=business_unit,
            limit=100,
        )

    async def get_situation_detail(self, situation_id: str) -> Optional[Situation]:
        return await self.situation_repository.get_situation(situation_id)

    async def update_situation_status(
        self, situation_id: str, new_status: SituationStatus
    ) -> Optional[Situation]:
        situation = await self.situation_repository.get_situation(situation_id)
        if situation:
            situation.status = new_status
            situation.updated_at = datetime.utcnow()
            await self.situation_repository.update_situation(situation)
        return situation
