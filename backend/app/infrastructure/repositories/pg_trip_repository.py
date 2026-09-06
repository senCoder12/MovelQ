from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

import structlog

from app.domain.entities import Trip
from app.domain.interfaces import TripRepository
from app.infrastructure.database import fetch_one, fetch_rows

logger = structlog.get_logger()


class PgTripRepository(TripRepository):
    """PostgreSQL / Neon implementation of TripRepository."""

    def _row_to_trip(self, row: dict) -> Trip:
        return Trip(**row)

    async def get_trip(self, trip_id: int) -> Optional[Trip]:
        sql = "SELECT * FROM analytics.v_trip WHERE trip_id = $1"
        row = await fetch_one(sql, trip_id)
        return self._row_to_trip(dict(row)) if row else None

    async def get_trips_for_shift(
        self,
        business_unit: str,
        office: str,
        shift: str,
        direction: str,
        trip_date: date,
    ) -> List[Trip]:
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
        if direction:
            params.append(direction)
            conditions.append(f"trip_direction = ${len(params)}")

        where = " AND ".join(conditions)
        sql = f"SELECT * FROM analytics.v_trip WHERE {where}"
        rows = await fetch_rows(sql, *params)
        return [self._row_to_trip(dict(r)) for r in rows]

    async def get_trips_for_date(
        self,
        trip_date: date,
        business_unit: Optional[str] = None,
    ) -> List[Trip]:
        conditions = ["trip_date = $1"]
        params: list[Any] = [trip_date]
        if business_unit:
            params.append(business_unit)
            conditions.append(f"business_unit = ${len(params)}")
        where = " AND ".join(conditions)
        sql = f"SELECT * FROM analytics.v_trip WHERE {where}"
        rows = await fetch_rows(sql, *params)
        return [self._row_to_trip(dict(r)) for r in rows]

    async def get_trip_count(
        self,
        business_unit: Optional[str] = None,
        office: Optional[str] = None,
        trip_date: Optional[date] = None,
    ) -> int:
        conditions = []
        params: list[Any] = []
        if business_unit:
            params.append(business_unit)
            conditions.append(f"business_unit = ${len(params)}")
        if office:
            params.append(office)
            conditions.append(f"office = ${len(params)}")
        if trip_date:
            params.append(trip_date)
            conditions.append(f"trip_date = ${len(params)}")

        where = " AND ".join(conditions) if conditions else "1=1"
        sql = f"SELECT COUNT(*) as count FROM analytics.v_trip WHERE {where}"
        row = await fetch_one(sql, *params)
        return row["count"] if row else 0

    async def get_shift_summary(
        self,
        business_unit: str,
        office: str,
        trip_date: date,
        vendor: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        conditions = ["trip_date = $1"]
        params: list[Any] = [trip_date]

        if business_unit:
            params.append(business_unit)
            conditions.append(f"business_unit = ${len(params)}")
        if office:
            params.append(office)
            conditions.append(f"office = ${len(params)}")
        if vendor:
            params.append(vendor)
            conditions.append(f"vendor = ${len(params)}")

        conditions.append("shift IS NOT NULL AND shift <> ''")
        where = " AND ".join(conditions)
        sql = f"""
            SELECT business_unit, office, shift, trip_direction as direction, 
                   COALESCE(AVG(delay_minutes), 0) as avg_delay,
                   COALESCE(AVG(CASE WHEN is_on_time THEN 1.0 ELSE 0.0 END) * 100, 100.0) as on_time_pct,
                   COUNT(*) as trip_count,
                   COALESCE(SUM(noshow_cnt), 0) as noshow_count,
                   COALESCE(SUM(actual_employee_cnt), 0) as actual_employee_cnt,
                   COALESCE(SUM(planned_employee_cnt), 0) as planned_employee_cnt,
                   COALESCE(SUM(CASE WHEN is_on_time THEN COALESCE(riders_actual, actual_employee_cnt, 0) ELSE 0 END), 0) as ready_on_time_cnt,
                   COALESCE(SUM(CASE WHEN NOT is_on_time THEN COALESCE(riders_actual, actual_employee_cnt, 0) ELSE 0 END), 0) as late_cnt
            FROM analytics.v_trip
            WHERE {where}
            GROUP BY business_unit, office, shift, trip_direction
            ORDER BY shift, office
        """
        rows = await fetch_rows(sql, *params)
        return [dict(r) for r in rows]

    async def get_delay_distribution(
        self,
        business_unit: str,
        office: str,
        shift: Optional[str] = None,
        direction: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Dict[str, Any]:
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
        if direction:
            params.append(direction)
            conditions.append(f"trip_direction = ${len(params)}")
        if start_date:
            params.append(start_date)
            conditions.append(f"trip_date >= ${len(params)}")
        if end_date:
            params.append(end_date)
            conditions.append(f"trip_date <= ${len(params)}")

        where = " AND ".join(conditions) if conditions else "1=1"
        sql = f"""
            SELECT 
                percentile_cont(0.50) within group (order by delay_minutes) as p50,
                percentile_cont(0.90) within group (order by delay_minutes) as p90,
                percentile_cont(0.95) within group (order by delay_minutes) as p95,
                percentile_cont(0.99) within group (order by delay_minutes) as p99
            FROM analytics.v_trip
            WHERE {where}
        """
        row = await fetch_one(sql, *params)
        return dict(row) if row else {}

    async def get_vendor_metrics(
        self,
        business_unit: str,
        office: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[Dict[str, Any]]:
        conditions = []
        params: list[Any] = []
        if business_unit:
            params.append(business_unit)
            conditions.append(f"business_unit = ${len(params)}")
        if office:
            params.append(office)
            conditions.append(f"office = ${len(params)}")
        if start_date:
            params.append(start_date)
            conditions.append(f"trip_date >= ${len(params)}")
        if end_date:
            params.append(end_date)
            conditions.append(f"trip_date <= ${len(params)}")

        where = " AND ".join(conditions) if conditions else "1=1"
        sql = f"""
            SELECT vendor, COUNT(*) as trip_count,
                   AVG(CASE WHEN is_on_time THEN 1.0 ELSE 0.0 END) * 100 as on_time_pct,
                   AVG(delay_minutes) as avg_delay,
                   percentile_cont(0.90) within group (order by delay_minutes) as p90_delay
            FROM analytics.v_trip
            WHERE {where}
            GROUP BY vendor
        """
        rows = await fetch_rows(sql, *params)
        return [dict(r) for r in rows]

    async def get_route_metrics(
        self,
        business_unit: str,
        office: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[Dict[str, Any]]:
        conditions = []
        params: list[Any] = []
        if business_unit:
            params.append(business_unit)
            conditions.append(f"business_unit = ${len(params)}")
        if office:
            params.append(office)
            conditions.append(f"office = ${len(params)}")
        if start_date:
            params.append(start_date)
            conditions.append(f"trip_date >= ${len(params)}")
        if end_date:
            params.append(end_date)
            conditions.append(f"trip_date <= ${len(params)}")

        where = " AND ".join(conditions) if conditions else "1=1"
        sql = f"""
            SELECT route_source, trip_nodal, COUNT(*) as trip_count
            FROM analytics.v_trip
            WHERE {where}
            GROUP BY route_source, trip_nodal
        """
        rows = await fetch_rows(sql, *params)
        return [dict(r) for r in rows]
