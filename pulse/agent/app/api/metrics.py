"""GET /api/metrics/cost -- what the model calls cost.

Served by the *agent*, not the backend, despite the /api prefix: the ledger
query and the rate table both live here (app/llm/cost.py, app/llm/rates.yaml),
and routing the query through Java would mean a second copy of the rate table.
Call it against the agent's port directly -- the frontend dev proxy sends /api
to the backend, and this endpoint is an operator/CLI surface, not a UI one:

    curl 'http://localhost:8000/api/metrics/cost?tenant_id=catalyst&format=text'

``format=text`` returns the fixed-width block meant for pasting into a slide;
the default JSON carries the same numbers for anything that wants to compute
with them.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse

from app.llm import cost

router = APIRouter(prefix="/api/metrics", tags=["metrics"])


@router.get("/cost")
def llm_cost(
    tenant_id: str = Query(..., min_length=1, description="tenant to report on"),
    start: str | None = Query(None, description="inclusive start date, YYYY-MM-DD"),
    end: str | None = Query(None, description="inclusive end date, YYYY-MM-DD"),
    format: str = Query("json", pattern="^(json|text)$"),
) -> Any:
    try:
        report = cost.cost_report(tenant_id, start, end)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        # The platform database is unreachable or the ledger table is missing.
        # A 503 rather than a zeroed report: "nothing ran" and "we cannot see
        # what ran" are different answers and must not look alike.
        raise HTTPException(status_code=503, detail=f"token ledger unavailable: {exc}") from exc

    if format == "text":
        return PlainTextResponse(cost.as_text(report))
    # Both shapes in the JSON too, so a copy-paste needs no second request.
    return {**report, "text": cost.as_text(report)}
