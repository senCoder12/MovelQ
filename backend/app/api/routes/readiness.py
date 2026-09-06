"""Readiness endpoints."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Query

from app.api.dependencies import get_readiness_service

router = APIRouter()


@router.get("/readiness")
async def get_readiness(
    business_unit: str = Query(default="", description="Filter by business unit"),
    date_str: str = Query(default="", alias="date", description="Date YYYY-MM-DD"),
):
    """Get shift readiness for all shifts on a given date.

    Returns deterministic, explainable readiness calculations.
    """
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
