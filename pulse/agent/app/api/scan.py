"""POST /internal/scan -- one detection pass, with the counts a scan_run needs.

The backend orchestrates the scan (it owns Postgres and therefore scan_run,
brief_snapshot and the insight tables); this endpoint is the warehouse half of
it. One call, one pass over DuckDB, and the window/trip-count/signal-count the
run row has to record come back with the insights rather than costing three more
round trips to ask for separately.

``GET /insights`` stays as it was for anything that just wants the packets.

Nothing here can reach a model: the whole signal path is LLM-free, which is what
tests/test_no_llm_imports.py enforces and what makes a degraded-mode scan able to
produce every figure with zero ledger rows behind it.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.detect import signals

router = APIRouter(prefix="/internal", tags=["internal"])


@router.post("/scan")
def scan(
    tenant_id: str = Query(..., min_length=1, description="tenant to scan"),
    lookback_days: int = Query(
        signals.DEFAULT_LOOKBACK_DAYS, ge=1, le=365,
        description="days back from the warehouse's latest trip date -- not from today",
    ),
) -> dict[str, Any]:
    try:
        return signals.scan(tenant_id, lookback_days)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
