from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

import structlog

from app.domain.entities import EmployeeTrip
from app.domain.interfaces import EmployeeRepository
from app.infrastructure.database import fetch_one, fetch_rows

logger = structlog.get_logger()


class PgEmployeeRepository(EmployeeRepository):
    """PostgreSQL / Neon implementation of EmployeeRepository."""

    def _row_to_employee(self, row: dict) -> EmployeeTrip:
        return EmployeeTrip(**row)

    async def get_employees_for_trip(self, trip_id: int) -> List[EmployeeTrip]:
        sql = "SELECT * FROM analytics.v_leg WHERE trip_id = $1"
        rows = await fetch_rows(sql, trip_id)
        return [self._row_to_employee(dict(r)) for r in rows]

    async def get_employees_for_shift(
        self,
        business_unit: str,
        office: str,
        shift: str,
        direction: Optional[str] = None,
        trip_date: Optional[date] = None,
    ) -> List[EmployeeTrip]:
        conditions = []
        params: list[Any] = []

        if business_unit:
            params.append(business_unit)
            conditions.append(f"business_unit = ${len(params)}")
        if office:
            params.append(office)
            conditions.append(f"office = ${len(params)}")
        if shift:
            params.append(shift)
            conditions.append(f"shift = ${len(params)}")
        if trip_date:
            params.append(trip_date)
            conditions.append(f"trip_date = ${len(params)}")

        where = " AND ".join(conditions) if conditions else "1=1"
        sql = f"SELECT * FROM analytics.v_leg WHERE {where}"
        rows = await fetch_rows(sql, *params)
        return [self._row_to_employee(dict(r)) for r in rows]

    async def get_affected_employees(self, trip_ids: List[int]) -> List[EmployeeTrip]:
        if not trip_ids:
            return []
        sql = "SELECT * FROM analytics.v_leg WHERE trip_id = ANY($1::bigint[])"
        rows = await fetch_rows(sql, trip_ids)
        return [self._row_to_employee(dict(r)) for r in rows]

    async def get_shift_employee_stats(
        self,
        business_unit: str,
        office: str,
        shift: str,
        direction: str,
        trip_date: date,
    ) -> Dict[str, Any]:
        conditions = ["trip_date = $1"]
        params: list[Any] = [trip_date]

        if business_unit:
            params.append(business_unit)
            conditions.append(f"business_unit = ${len(params)}")
        if office:
            params.append(office)
            conditions.append(f"office = ${len(params)}")
        if shift:
            params.append(shift)
            conditions.append(f"shift = ${len(params)}")

        where = " AND ".join(conditions)
        sql = f"""
            SELECT COUNT(*) as total_employees,
                   SUM(CASE WHEN LOWER(boarding_status) = 'boarded' THEN 1 ELSE 0 END) as boarded,
                   SUM(CASE WHEN LOWER(boarding_status) = 'not boarded' THEN 1 ELSE 0 END) as not_boarded,
                   SUM(CASE WHEN is_no_show THEN 1 ELSE 0 END) as no_shows,
                   SUM(CASE WHEN is_late_pickup THEN 1 ELSE 0 END) as late_pickups,
                   SUM(CASE WHEN LOWER(boarding_status) = 'boarded' AND NOT is_late_pickup THEN 1 ELSE 0 END) as boarded_on_time_cnt,
                   SUM(CASE WHEN NOT is_late_pickup AND NOT is_no_show THEN 1 ELSE 0 END) as on_time_count
            FROM analytics.v_leg
            WHERE {where}
        """
        row = await fetch_one(sql, *params)
        return dict(row) if row else {
            "total_employees": 0,
            "boarded": 0,
            "not_boarded": 0,
            "no_shows": 0,
            "late_pickups": 0,
            "boarded_on_time_cnt": 0,
            "on_time_count": 0,
        }
