"""Simulate Alert -- manual test entry point for the alert pipeline.

Inserts a row the same way a real alert arrives (staging.alerts_data, plus
a matching core.fact_trip so it isn't an orphan), and lets db/09_alert_stream_trigger.sql's
trigger + AlertStreamService take it from there. Priority controls severity_raw,
which is exactly what core.fn_is_important_alert() gates on:
  HIGH -> Sev-1 -> important -> notified -> situation created -> dashboard
  LOW  -> Sev-3 -> not important -> never notified -> nothing on the dashboard
Both land in core.fact_alert either way -- "low priority" means filtered
before the dashboard, not dropped from the database.
"""

from __future__ import annotations

import asyncio
import random
import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.dependencies import get_situation_service
from app.infrastructure.database import execute

router = APIRouter()

_SEVERITY_BY_PRIORITY = {"HIGH": "Sev-1", "LOW": "Sev-3"}
_DELAY_MINUTES_BY_PRIORITY = {"HIGH": 40, "LOW": 5}


class SimulateAlertRequest(BaseModel):
    alert_name: str
    priority: str  # "HIGH" | "LOW"


def _sanitize_event_type(name: str) -> str:
    cleaned = "".join(c if c.isalnum() else "_" for c in name.strip().upper())
    cleaned = "_".join(part for part in cleaned.split("_") if part)
    return cleaned or "CUSTOM_ALERT"


@router.post("/simulate-alert")
async def simulate_alert(req: SimulateAlertRequest):
    priority = req.priority.strip().upper()
    if priority not in _SEVERITY_BY_PRIORITY:
        return {"error": "priority must be 'HIGH' or 'LOW'"}

    trip_id = 900_000_000 + random.randint(0, 99_999_999)
    event_id = str(uuid.uuid4())
    event_type = _sanitize_event_type(req.alert_name)
    severity = _SEVERITY_BY_PRIORITY[priority]
    delay_minutes = _DELAY_MINUTES_BY_PRIORITY[priority]

    business_unit = "vanta-Aus"
    business_unit_key = 4
    office_key = 5  # Santa Clara Office -- belongs to business_unit_key 4

    now = datetime.now(timezone.utc)
    trip_date = date.today()

    await execute(
        """
        INSERT INTO core.fact_trip (
            trip_id, trip_date, business_unit_key, office_key, vendor_key, shift_key,
            product_type, trip_direction, trip_nodal, route_source, delay_reason,
            actual_escort, is_driver_nc, is_cab_nc,
            planned_km, traveled_km,
            planned_start_ts, planned_end_ts, actual_start_ts, actual_end_ts,
            delay_minutes, planned_employee_cnt, actual_employee_cnt, noshow_cnt,
            source_file
        ) VALUES (
            $1,$2,$3,$4,$5,$6,'CAB','LOGIN','HOME','AUTO','TRAFFIC',
            false,false,false, 10.0,10.5, $7,$8,$7,$8, $9,4,4,0,'simulated_alert'
        ) ON CONFLICT (trip_id) DO NOTHING
        """,
        trip_id, trip_date, business_unit_key, office_key, 5, None,
        now, now, delay_minutes,
    )

    ts_text = now.strftime("%B %d, %Y, %I:%M %p")
    await execute(
        """
        INSERT INTO staging.alerts_data (
            business_unit, trip_id, stwid, event_id, event_type,
            start_time, acknowledge_time, state_text, severity, source
        ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
        """,
        business_unit, str(trip_id), "0", event_id, event_type,
        ts_text, ts_text, "CLOSED", severity, "SIMULATED",
    )

    situation_created = False
    if priority == "HIGH":
        situation_svc = get_situation_service()
        for _ in range(8):
            await asyncio.sleep(0.5)
            situations = await situation_svc.get_active_situations()
            if any(trip_id in s.trip_ids for s in situations):
                situation_created = True
                break

    if priority == "LOW":
        message = "Low-priority alert logged to the database. Filtered out before the dashboard, by design."
    elif situation_created:
        message = "High-priority alert processed: situation created and now visible on the dashboard."
    else:
        message = "High-priority alert inserted, but no situation appeared yet -- check backend logs."

    return {
        "trip_id": trip_id,
        "event_id": event_id,
        "event_type": event_type,
        "priority": priority,
        "severity": severity,
        "situation_created": situation_created,
        "message": message,
    }
