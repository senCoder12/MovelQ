from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

import structlog

from app.domain.entities import Alert
from app.domain.interfaces import AlertRepository
from app.infrastructure.database import fetch_rows

logger = structlog.get_logger()


class PgAlertRepository(AlertRepository):
    """PostgreSQL / Neon implementation of AlertRepository."""

    def _row_to_alert(self, row: dict) -> Alert:
        data = dict(row)
        if data.get("event_id") is not None:
            data["event_id"] = str(data["event_id"])
        return Alert(**data)

    async def get_alerts_for_trip(self, trip_id: int) -> List[Alert]:
        sql = "SELECT * FROM analytics.v_alert WHERE trip_id = $1 ORDER BY start_ts"
        rows = await fetch_rows(sql, trip_id)
        return [self._row_to_alert(r) for r in rows]

    async def get_alerts_for_date(
        self, business_unit: str, alert_date: date
    ) -> List[Alert]:
        conditions = ["alert_date = $1"]
        params: list[Any] = [alert_date]
        if business_unit:
            params.append(business_unit)
            conditions.append(f"business_unit = ${len(params)}")

        where = " AND ".join(conditions)
        sql = f"SELECT * FROM analytics.v_alert WHERE {where} ORDER BY start_ts"
        rows = await fetch_rows(sql, *params)
        return [self._row_to_alert(r) for r in rows]

    async def get_alert_counts_by_type(
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
            conditions.append(f"alert_date >= ${len(params)}")
        if end_date:
            params.append(end_date)
            conditions.append(f"alert_date <= ${len(params)}")

        where = " AND ".join(conditions) if conditions else "1=1"
        sql = f"""
            SELECT event_type, alert_scope, COUNT(*) as count
            FROM analytics.v_alert
            WHERE {where}
            GROUP BY event_type, alert_scope
        """
        rows = await fetch_rows(sql, *params)
        return [dict(r) for r in rows]
