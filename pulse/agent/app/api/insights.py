"""GET /insights -- detected signals for one tenant.

Insights are computed on request from the warehouse rather than stored here: the
agent owns DuckDB and nothing else, and the Java backend is the only thing that
holds Postgres credentials. The backend calls this, persists what comes back, and
serves the API from Postgres -- so a slow detection pass never sits in front of a
user, and the agent stays stateless.

Every endpoint is tenant-scoped and says so in its signature. app/db.py refuses a
query with no tenant, so there is no unscoped path to fall into.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.detect import signals

router = APIRouter(tags=["insights"])


@router.get("/tenants")
def list_tenants() -> list[str]:
    """Tenants present in the warehouse, so the backend can refresh all of them
    without a hardcoded list."""
    return signals.tenants()


@router.get("/insights")
def list_insights(
    tenant_id: str = Query(..., min_length=1, description="tenant to detect for"),
    start: str | None = Query(None, description="window start; defaults to the metric's full range"),
    end: str | None = Query(None, description="window end; defaults to the metric's full range"),
) -> list[dict[str, Any]]:
    try:
        return signals.detect_tenant(tenant_id, start, end)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/insights/{insight_id}")
def get_insight(
    insight_id: str,
    tenant_id: str = Query(..., min_length=1),
) -> dict[str, Any]:
    for insight in signals.detect_tenant(tenant_id):
        if insight["insight_id"] == insight_id:
            return insight
    raise HTTPException(status_code=404, detail=f"unknown insight_id: {insight_id}")


@router.get("/insights/{insight_id}/trace")
def get_trace(
    insight_id: str,
    tenant_id: str = Query(..., min_length=1),
) -> dict[str, Any]:
    insight = get_insight(insight_id, tenant_id)
    return {"insight_id": insight_id, "trace": insight["trace"]}
