from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, Optional

import structlog

from app.domain.entities import HistoricalBaseline
from app.domain.interfaces import BaselineRepository
from app.infrastructure.database import fetch_one

logger = structlog.get_logger()


class PgBaselineRepository(BaselineRepository):
    """PostgreSQL / Neon implementation of BaselineRepository."""

    def __init__(self):
        self._cache: Dict[str, Any] = {}

    async def get_shift_baseline(
        self,
        business_unit: str,
        office: str,
        shift: str,
        direction: str,
        lookback_days: int = 30,
        reference_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        ref = reference_date or date(2026, 7, 15)
        cache_key = f"shift_base:{business_unit}:{office}:{shift}:{direction}:{lookback_days}:{ref}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        start_date = ref - timedelta(days=lookback_days)
        end_date = ref - timedelta(days=1)

        conditions = ["trip_date >= $1", "trip_date <= $2"]
        params: list[Any] = [start_date, end_date]

        if business_unit:
            params.append(business_unit)
            conditions.append(f"business_unit = ${len(params)}")
        if office:
            params.append(office)
            conditions.append(f"office = ${len(params)}")
        if shift:
            params.append(shift)
            conditions.append(f"shift = ${len(params)}")
        if direction:
            params.append(direction)
            conditions.append(f"trip_direction = ${len(params)}")

        where = " AND ".join(conditions)
        sql = f"""
            SELECT 
                AVG(delay_minutes) as avg_delay,
                percentile_cont(0.50) within group (order by delay_minutes) as median_delay,
                percentile_cont(0.90) within group (order by delay_minutes) as p90_delay,
                percentile_cont(0.95) within group (order by delay_minutes) as p95_delay,
                AVG(CASE WHEN is_on_time THEN 1.0 ELSE 0.0 END) * 100 as on_time_pct,
                AVG(CASE WHEN planned_employee_cnt > 0 THEN riders_actual::float / planned_employee_cnt ELSE 1.0 END) as readiness_score_mean,
                AVG(noshow_cnt) as avg_noshow_rate,
                COUNT(*) as trip_count,
                AVG(actual_employee_cnt) as avg_employee_cnt
            FROM analytics.v_trip
            WHERE {where}
        """
        row = await fetch_one(sql, *params)
        res = dict(row) if row else {
            "avg_delay": 0.0,
            "median_delay": 0.0,
            "p90_delay": 0.0,
            "p95_delay": 0.0,
            "on_time_pct": 95.0,
            "readiness_score_mean": 0.92,
            "avg_noshow_rate": 0.0,
            "trip_count": 0,
            "avg_employee_cnt": 0,
        }
        self._cache[cache_key] = res
        return res

    async def get_baseline(
        self,
        metric_name: str,
        office: str,
        shift: Optional[str] = None,
        direction: Optional[str] = None,
        period_label: str = "30d",
    ) -> Optional[HistoricalBaseline]:
        key = f"{metric_name}_{office}_{shift or ''}_{direction or ''}_{period_label}"
        return self._cache.get(key)

    async def save_baseline(self, baseline: HistoricalBaseline) -> None:
        key = f"{baseline.metric_name}_{baseline.scope}_{baseline.period_label}"
        self._cache[key] = baseline
