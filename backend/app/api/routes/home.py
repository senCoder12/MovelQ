"""Home / Command Center endpoint.

Returns the primary view for the Line Manager persona:
current readiness, active situations, recommended actions.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import (
    get_readiness_service,
    get_situation_service,
    get_trip_repo,
)
from app.core.cache import cache

router = APIRouter()


@router.get("/home")
async def get_home(
    business_unit: str = Query(default="", description="Filter by business unit"),
    trip_date: str = Query(default="", description="Date in YYYY-MM-DD format"),
):
    """Command center — readiness, situations, and recommended actions."""

    target_date = date.fromisoformat(trip_date) if isinstance(trip_date, str) and trip_date else date(2026, 7, 15)
    bu = business_unit if isinstance(business_unit, str) and business_unit else None

    cache_key = f"home_dashboard:{bu or 'ALL'}:{target_date}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    readiness_svc = get_readiness_service()
    situation_svc = get_situation_service()
    trip_repo = get_trip_repo()

    # Get all shift readiness
    try:
        readiness_list = await readiness_svc.get_all_shift_readiness(
            business_unit=bu,
            trip_date=target_date,
        )
    except Exception:
        readiness_list = []

    # Get active situations
    try:
        situations = await situation_svc.get_active_situations(business_unit=bu)
    except Exception:
        situations = []

    # Overall stats
    try:
        total_trips = await trip_repo.get_trip_count(
            business_unit=bu,
            trip_date=target_date,
        )
    except Exception:
        total_trips = 0

    # Calculate overall readiness
    total_expected = sum(r.employees_expected for r in readiness_list)
    total_ready = sum(r.employees_ready_on_time for r in readiness_list)
    overall_readiness = total_ready / total_expected if total_expected > 0 else 0.0

    total_at_risk = sum(r.employees_at_risk for r in readiness_list)

    res = {
        "readiness_summary": [r.model_dump() for r in readiness_list],
        "active_situations": [s.model_dump() for s in situations],
        "recent_actions": [],
        "stats": {
            "total_trips": total_trips,
            "total_employees": total_expected,
            "active_situations": len(situations),
            "overall_readiness": round(overall_readiness, 4),
            "employees_at_risk": total_at_risk,
        },
    }
    cache.set(cache_key, res, ttl=600.0)
    return res
