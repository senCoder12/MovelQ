from __future__ import annotations

import math
from typing import Any, List, Optional

import structlog

from app.domain.entities import EmployeeTrip, Situation, SituationImpact, Trip

logger = structlog.get_logger(__name__)


class ImpactService:
    """Deterministic situation impact analysis engine.

    Quantifies affected employees, trip delays, routes, readiness impacts,
    and cost figures without using an LLM.
    """

    def calculate_impact(
        self,
        situation: Situation,
        trips: List[Trip],
        employees: Optional[List[EmployeeTrip]] = None,
        historical_delay_p95: Optional[float] = None,
        readiness_delta_pp: Optional[float] = None,
    ) -> SituationImpact:
        affected_trips = len(trips)

        # Count affected employees
        if employees:
            affected_employees = len(employees)
        else:
            affected_employees = sum((t.planned_employee_cnt or 0) for t in trips)

        # Delays
        delays = [float(t.delay_minutes or 0) for t in trips if t.delay_minutes is not None]
        delay_total = int(sum(delays))

        delay_p95 = None
        if delays:
            delays.sort()
            idx = max(0, int(math.ceil(0.95 * len(delays))) - 1)
            delay_p95 = round(delays[idx], 1)

        # Routes / Nodals
        routes = {t.route_source for t in trips if t.route_source}
        affected_routes = max(1, len(routes)) if affected_trips > 0 else 0

        # Noshow count
        noshow_count = sum((t.noshow_cnt or 0) for t in trips)

        # Estimated cost impact (heuristic: ~400 INR per delayed trip hour)
        cost_impact = round((delay_total / 60.0) * 400.0, 2) if delay_total > 0 else None

        return SituationImpact(
            affected_employees=affected_employees,
            affected_trips=affected_trips,
            affected_routes=affected_routes,
            delay_minutes_total=delay_total,
            delay_p95=delay_p95,
            historical_delay_p95=historical_delay_p95,
            readiness_delta_pp=readiness_delta_pp,
            cost_impact=cost_impact,
            noshow_count=noshow_count,
        )
