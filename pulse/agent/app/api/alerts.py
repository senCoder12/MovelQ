"""POST /internal/evaluate-alerts -- deterministic alert routing.

Java has already fetched the tenant's insights and posts them here
alongside every (entity_dim, entity_id) that has ever fired an alert
before (for the new_entity condition -- this module keeps no history of
its own, see app/detect/alert_router.py's module docstring). The response
is a list of candidate matches; Java applies cooldown and suppression on
top and persists whatever survives. No LLM call happens anywhere in this
path -- alerting is routing over content the scan already produced.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.detect import alert_router

router = APIRouter(prefix="/internal", tags=["internal"])


@router.post("/evaluate-alerts")
def evaluate_alerts(payload: dict[str, Any]) -> dict[str, Any]:
    insights = payload.get("insights") or []
    known_entities = {tuple(pair) for pair in payload.get("known_entities") or []}

    ranked = alert_router.rank_and_dedupe(insights)
    candidates = alert_router.evaluate(ranked, known_entities=known_entities)

    return {
        "candidates": candidates,
        "ranked_insight_ids": [insight["insight_id"] for insight in ranked],
    }
