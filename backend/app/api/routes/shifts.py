"""Shift overview endpoints."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Query

from app.api.dependencies import get_readiness_service, get_trip_repo

router = APIRouter()


@router.get("/shifts")
async def get_shifts(
    business_unit: str = Query(default="", description="Filter by business unit"),
    date_str: str = Query(default="", alias="date", description="Date YYYY-MM-DD"),
):
    """Get shift summaries with readiness for a given date."""
    readiness_svc = get_readiness_service()
    target_date = date.fromisoformat(date_str) if isinstance(date_str, str) and date_str else date(2026, 7, 15)
    bu = business_unit if isinstance(business_unit, str) and business_unit else None

    try:
        readiness_list = await readiness_svc.get_all_shift_readiness(
            business_unit=bu,
            trip_date=target_date,
        )
        return [r.model_dump() for r in readiness_list]
    except Exception as e:
        return []


@router.get("/shifts/{shift_id}")
async def get_shift_detail(
    shift_id: str,
    business_unit: str = Query(default=""),
    date_str: str = Query(default="", alias="date"),
):
    """Get detailed shift information including readiness and trip breakdown."""
    trip_repo = get_trip_repo()
    target_date = date.fromisoformat(date_str) if date_str else date(2026, 7, 15)

    try:
        summary = await trip_repo.get_shift_summary(
            business_unit=business_unit or "catalyst-Slc",
            office="Oakmont",
            trip_date=target_date,
        )
        return {"shift_id": shift_id, "summary": summary}
    except Exception:
        return {"shift_id": shift_id, "summary": []}
