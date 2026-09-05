"""Standalone mock of the agent service. Hardcoded InsightPacket objects,
shaped to validate against contracts/insight.schema.json. No DuckDB, no
imports from agent/app -- this is the contract Angular/Java build against
while real ingest/detection land.

Run: python scripts/mock_agent.py   (serves on :8000, same port as the real agent)
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

app = FastAPI(title="pulse-mock-agent", version="0.1.0")

INSIGHTS: dict[str, dict] = {
    "ins_001": {
        "insight_id": "ins_001", "severity": 92,
        "metric": {"id": "delay_reconciliation_gap", "name": "Delay reconciliation gap (reported vs computed)",
                    "value": 54.5, "unit": "%", "n": 215885, "window": "trailing_30d"},
        "entity": {"dim": "fleet", "id": "ALL", "name": "Fleet-wide"},
        "references": [
            {"type": "peer", "label": "next-worst shift-suffix contradiction rate", "value": 38.2, "unit": "percent"},
            {"type": "computed", "label": "mean reported delay_minutes", "value": 1.38, "unit": "minutes"},
            {"type": "computed", "label": "mean computed_arrival_delay_min", "value": 9.87, "unit": "minutes"},
            {"type": "computed", "label": "share of all trips in ':16' shift codes", "value": 14.15, "unit": "percent"},
        ],
        "attribution": [
            {"dim": "shift_suffix", "value": ":16", "contribution_pct": 58.4, "n": 29854},
            {"dim": "vendor_id", "value": "Vikram Mikhailov Travel", "contribution_pct": 55.0, "n": 9417},
        ],
        "controls": [
            {"control": "hour_of_day", "gap_pp": 47.6, "survives": True},
            {"control": "vendor", "gap_pp": 55.1, "survives": True},
        ],
        "coincident_events": [],
        "impact": {"affected_trips": 117605},
        "data_quality": {"excluded_pct": 0.0, "confidence": "high"},
        "trace": [
            {"query_id": "suffix_table", "params": {"group_by": "shift_type_suffix"},
             "numerator": 117605, "denominator": 215885, "exclusions": [],
             "validation": {"status": "pass", "notes": "row counts reconcile against raw ingest table"}},
            {"query_id": "vendor_control_8e", "params": {"hours": [16, 17, 18, 19]},
             "numerator": 9417, "denominator": 17111, "exclusions": ["trips missing vendor_id (0.4%)"],
             "validation": {"status": "pass", "notes": "gap survives hour-of-day and vendor controls"}},
        ],
        "narrative": {
            "headline": "117,605 trips arrived late while reporting zero delay",
            "body": "54.5% of trips report delay_minutes as zero/null while computed_arrival_delay_min "
                    "exceeds 10 minutes. The ':16' shift-suffix cluster carries 58.4% of the contradiction "
                    "and the gap survives both hour-of-day and vendor controls.",
            "recommended_actions": [
                {"type": "ticket", "title": "Investigate ':16' shift-code delay capture gap",
                 "draft": "Rostering/scheduling path for ':16' shift_type codes never writes delay_minutes.",
                 "rationale": "58.4% attribution, survives hour and vendor controls."},
            ],
        },
    },
    "ins_002": {
        "insight_id": "ins_002", "severity": 71,
        "metric": {"id": "escort_coverage_night_female", "name": "Night escort coverage (female employees)",
                    "value": 60.8, "unit": "%", "n": 81174, "window": "trailing_30d"},
        "entity": {"dim": "segment", "id": "night_female_escort", "name": "Night trips, female employees"},
        "references": [{"type": "historical", "label": "baseline escort rate across all legs", "value": 20.2, "unit": "percent"}],
        "attribution": [
            {"dim": "vendor_id", "value": "Sneha Mikhailov Travel", "contribution_pct": 61.0, "n": 14620},
            {"dim": "vendor_id", "value": "Meera Pavlov Travel", "contribution_pct": 59.7, "n": 11940},
        ],
        "controls": [],
        "coincident_events": [],
        "impact": {"affected_trips": 31838},
        "data_quality": {"excluded_pct": 0.0, "confidence": "medium"},
        "trace": [{"query_id": "escort_coverage_by_vendor", "params": {"segment": "night_female"},
                   "numerator": 49336, "denominator": 81174, "exclusions": [],
                   "validation": {"status": "warn", "notes": "vendor roster join has 2 unmatched vendor_ids"}}],
        "narrative": {
            "headline": "Night escort coverage for female employees stops at 61%",
            "body": "60.8% coverage (31,838 of 81,174 legs uncovered), well above the 20.2% baseline "
                    "escort rate across all legs but plateaued short of full coverage.",
            "recommended_actions": [
                {"type": "ticket", "title": "Escalate escort gap to lowest-coverage vendors",
                 "draft": "Sneha Mikhailov Travel and Meera Pavlov Travel lag fleet coverage on night/female legs.",
                 "rationale": "Two vendors account for the bulk of uncovered legs."},
            ],
        },
    },
    "ins_003": {
        "insight_id": "ins_003", "severity": 58,
        "metric": {"id": "ev_contract_mismatch_rate", "name": "EV-contract trips run on non-EV fuel",
                    "value": 8.11, "unit": "%", "n": 25351, "window": "trailing_30d"},
        "entity": {"dim": "contract_type", "id": "EV", "name": "EV Contract"},
        "references": [{"type": "computed", "label": "expected fuel_type for EV contract", "value": "electric", "unit": "text"}],
        "attribution": [], "controls": [], "coincident_events": [],
        "impact": {"affected_trips": 2056, "cost_inr_month": 2870000.0},
        "data_quality": {"excluded_pct": 0.0, "confidence": "medium"},
        "trace": [{"query_id": "ev_contract_fuel_mismatch", "params": {"contract_type": "EV"},
                   "numerator": 2056, "denominator": 25351, "exclusions": [],
                   "validation": {"status": "pass", "notes": "fuel_type field non-null for all EV-contract rows"}}],
        "narrative": {
            "headline": "2,056 trips billed on EV contracts ran on petrol or diesel",
            "body": "8.11% of EV-contract rows (2,056 of 25,351) show actual_cab_fuel_type as petrol "
                    "or diesel instead of electric.",
            "recommended_actions": [
                {"type": "ticket", "title": "Audit EV-contract billing vs actual fuel type",
                 "draft": "2,056 trips billed under EV contract terms ran on non-electric vehicles.",
                 "rationale": "Direct billing/contract-compliance exposure."},
            ],
        },
    },
}


# Hardcoded response for POST /internal/leadership-narrative, keyed to the
# three insights above. Request body is accepted but ignored -- Angular and
# Java build against a fixed narrative while the real LLM path (agent/app/api
# /leadership.py) lands.
LEADERSHIP_NARRATIVE = {
    "headline": "Reported delay data is unreliable across half the fleet",
    "summary": (
        "July's 215,885 trips surface three reconciliation gaps worth board attention. "
        "Delay data is reliable for only 45.5% of trips, concentrated in a narrow set of "
        "shift codes. Night escort coverage for female employees has reached 60.8%, well "
        "above the fleet baseline but still incomplete. EV-contract fuel matched actual "
        "fuel type on 91.9% of trips, with the remainder representing a distinct billing "
        "exposure."
    ),
    "findings": [
        {
            "insight_id": "ins_001",
            "body": (
                "117,605 trips arrived late while reporting zero delay, 54.5% of the fleet. "
                "The ':16' shift-code cluster accounts for 14.15% of trips but 58.4% of the "
                "contradiction, against 38.2% for the next-worst cluster, and the gap "
                "survives both hour-of-day and vendor controls. One hypothesis, not yet "
                "confirmed, is that the scheduling path for ':16' codes never writes the "
                "delay field."
            ),
            "recommendation": "Audit the scheduling path for ':16' shift codes to confirm whether it writes the delay field.",
        },
        {
            "insight_id": "ins_002",
            "body": (
                "Night escort coverage for female employees stands at 60.8%, leaving "
                "31,838 of 81,174 legs uncovered. That is roughly double the 20.2% "
                "baseline escort rate across all legs, so targeting is working, but "
                "coverage has plateaued short of full coverage. Sneha Mikhailov Travel "
                "and Meera Pavlov Travel account for the bulk of the uncovered legs."
            ),
            "recommendation": "Close the coverage gap at Sneha Mikhailov Travel and Meera Pavlov Travel, the two lowest-covering vendors.",
        },
        {
            "insight_id": "ins_003",
            "body": (
                "2,056 trips billed under EV contract terms ran on petrol or diesel, "
                "8.11% of EV-contract rows and ₹2.87M in billing. This affects both cost "
                "recovery and sustainability reporting."
            ),
            "recommendation": "Reconcile contract type against actual fuel type at the billing stage.",
        },
    ],
}


@app.post("/internal/leadership-narrative")
def leadership_narrative(payload: dict) -> dict:
    return LEADERSHIP_NARRATIVE


@app.get("/health")
def health() -> dict:
    return {"status": "UP", "service": "pulse-mock-agent", "version": "0.1.0"}


@app.get("/insights")
def list_insights() -> list[dict]:
    return list(INSIGHTS.values())


@app.get("/insights/{insight_id}")
def get_insight(insight_id: str) -> dict:
    if insight_id not in INSIGHTS:
        raise HTTPException(status_code=404, detail=f"unknown insight_id: {insight_id}")
    return INSIGHTS[insight_id]


@app.get("/insights/{insight_id}/trace")
def get_trace(insight_id: str) -> JSONResponse:
    if insight_id not in INSIGHTS:
        raise HTTPException(status_code=404, detail=f"unknown insight_id: {insight_id}")
    return JSONResponse({"insight_id": insight_id, "trace": INSIGHTS[insight_id]["trace"]})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
