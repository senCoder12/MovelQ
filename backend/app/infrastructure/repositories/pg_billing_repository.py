from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

import structlog

from app.domain.interfaces import BillingRepository
from app.infrastructure.database import fetch_one, fetch_rows

logger = structlog.get_logger()


class PgBillingRepository(BillingRepository):
    """PostgreSQL / Neon implementation of BillingRepository."""

    async def get_cost_for_trips(self, trip_ids: List[int]) -> Dict[str, Any]:
        if not trip_ids:
            return {"sum_cost": 0.0, "count": 0, "avg_cost_per_km": 0.0}

        sql = """
            SELECT COALESCE(SUM(trip_cost), 0) as sum_cost,
                   COUNT(*) as count,
                   COALESCE(AVG(cost_per_km), 0) as avg_cost_per_km
            FROM analytics.v_billing
            WHERE trip_id = ANY($1::bigint[])
        """
        row = await fetch_one(sql, trip_ids)
        return dict(row) if row else {"sum_cost": 0.0, "count": 0, "avg_cost_per_km": 0.0}

    async def get_vendor_cost_metrics(
        self,
        business_unit: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[Dict[str, Any]]:
        conditions = []
        params: list[Any] = []
        if business_unit:
            params.append(business_unit)
            conditions.append(f"business_unit = ${len(params)}")
        if start_date:
            params.append(start_date)
            conditions.append(f"cycle_start >= ${len(params)}")
        if end_date:
            params.append(end_date)
            conditions.append(f"cycle_end <= ${len(params)}")

        where = " AND ".join(conditions) if conditions else "1=1"
        sql = f"""
            SELECT vendor, 
                   COALESCE(SUM(trip_cost), 0) as total_cost,
                   COALESCE(AVG(trip_cost), 0) as avg_cost_per_trip
            FROM analytics.v_billing
            WHERE {where}
            GROUP BY vendor
        """
        rows = await fetch_rows(sql, *params)
        return [dict(r) for r in rows]
