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
            {"type": "computed", "label": "nonzero reported delay_minutes within ':16' cohort", "value": 2, "unit": "count"},
            {"type": "computed", "label": "distinct vendors spanned by the vendor control", "value": 9, "unit": "count"},
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


# Hardcoded response for POST /internal/draft-action, keyed by (insight_id,
# type) -- Angular and Java build the drawer, persistence and approval flow
# against these while the real drafting path (agent/app/actions/drafters.py)
# lands. Every number below is copied verbatim from an INSIGHTS entry above,
# same grounding rule the real validator (agent/app/agent/validator.py)
# enforces -- see that module and agent/app/actions/drafters.py for why.
ACTION_DRAFTS: dict[tuple[str, str], dict] = {
    ("ins_001", "VENDOR_ESCALATION"): {
        "action_id": "act_001_vendor",
        "insight_id": "ins_001",
        "type": "VENDOR_ESCALATION",
        "title": "Escalate delay reporting gap to Vikram Mikhailov Travel",
        "recipient": {"role": "vendor_account_manager", "name": "Vikram Mikhailov Travel"},
        "channel": "email",
        "subject": "Delay reporting discrepancy -- Vikram Mikhailov Travel, 9,417 trips",
        "body": (
            "We are writing to flag a discrepancy between reported and observed delay figures on trips "
            "operated by Vikram Mikhailov Travel.\n\n"
            "Under the reporting terms of the contract, delay_minutes is expected to reflect the actual "
            "arrival delay for each trip. Across 9,417 trips attributed to Vikram Mikhailov Travel (55.0% "
            "of the fleet-wide contradiction we are tracking this period), the average reported delay is "
            "1.38 minutes against a computed average arrival delay of 9.87 minutes. This gap persists "
            "after controlling for vendor assignment (+55.1pp, survives), so it does not appear to be "
            "explained by which trips this vendor happens to run.\n\n"
            "We are unable to confirm the cause from our side and would appreciate your team's read on "
            "where the reporting gap originates -- for example, whether delay_minutes is being populated "
            "at the point of dispatch for these trips.\n\n"
            "The underlying trip-level data is available on request. We would appreciate a response by "
            "the end of next week."
        ),
        "facts_cited": [
            {"label": "Vendor", "value": "Vikram Mikhailov Travel", "source_field": "attribution[dim=vendor_id].value"},
            {"label": "Trips attributed to this vendor", "value": "9,417", "source_field": "attribution[dim=vendor_id].n"},
            {"label": "Share of the fleet-wide contradiction", "value": "55.0%",
             "source_field": "attribution[dim=vendor_id].contribution_pct"},
            {"label": "Mean reported delay (vendor-submitted)", "value": "1.38 minutes",
             "source_field": "references[label=mean reported delay_minutes].value"},
            {"label": "Mean computed arrival delay (observed)", "value": "9.87 minutes",
             "source_field": "references[label=mean computed_arrival_delay_min].value"},
            {"label": "Gap remaining after controlling for vendor", "value": "+55.1pp (survives)",
             "source_field": "controls[control=vendor]"},
        ],
        "preview": {
            "what_changes": "Approving records the decision to an approval log; no email is actually sent to the vendor.",
            "reversible": True,
        },
        "rationale": (
            "Vikram Mikhailov Travel accounts for 55.0% of this contradiction (9,417 trips) and the gap "
            "survives a vendor control -- concentrated enough to raise with the vendor directly."
        ),
        "confidence": "high",
    },
    ("ins_001", "SYSTEM_AUDIT_REQUEST"): {
        "action_id": "act_001_audit",
        "insight_id": "ins_001",
        "type": "SYSTEM_AUDIT_REQUEST",
        "title": "Audit request: ':16' shift-code delay-capture gap",
        "recipient": {"role": "platform_team", "name": "Platform team"},
        "channel": "ticket",
        "subject": "Audit request: ':16' shift-code delay-capture gap",
        "body": (
            "This is a request to audit the scheduling/write path for ':16' shift-type codes, not a "
            "conclusion.\n\n"
            "Hypothesis, not yet confirmed: the scheduling path for ':16' shift codes never writes the "
            "delay_minutes field, rather than those trips genuinely running on time.\n\n"
            "Evidence:\n"
            "- Of 29,854 trips in the ':16' cohort, only 2 have a nonzero reported delay_minutes value.\n"
            "- The gap survives a control for hour of day (+47.6pp, survives).\n"
            "- The gap survives a control for vendor, across all 9 vendors represented in that control "
            "(+55.1pp, survives).\n"
            "- We are unable to infer a start date for this pattern from the fields available to us.\n\n"
            "What would confirm it: source-system write logs for the ':16' scheduling path, showing "
            "whether delay_minutes is ever populated for these trips at write time.\n\n"
            "We would appreciate the platform team's read on this within the next two weeks."
        ),
        "facts_cited": [
            {"label": "Trips within ':16' shift-code cohort", "value": "29,854",
             "source_field": "attribution[dim=shift_suffix].n"},
            {"label": "Trips in that cohort with nonzero reported delay_minutes", "value": "2",
             "source_field": "references[label=nonzero reported delay_minutes].value"},
            {"label": "Gap remaining after controlling for hour of day", "value": "+47.6pp (survives)",
             "source_field": "controls[control=hour_of_day]"},
            {"label": "Gap remaining after controlling for vendor", "value": "+55.1pp (survives), spans 9 vendors",
             "source_field": "controls[control=vendor]"},
            {"label": "Start date of the pattern", "value": "not inferable from available fields",
             "source_field": "data_quality"},
        ],
        "preview": {
            "what_changes": "Approving records the decision to an approval log; no ticket is actually filed with the platform team.",
            "reversible": True,
        },
        "rationale": (
            "The ':16' cohort carries the bulk of the contradiction and the gap survives both hour-of-day "
            "and vendor controls, which rules out the obvious confounds -- only a look at the write path "
            "can confirm the mechanism."
        ),
        "confidence": "high",
    },
    ("ins_002", "ESCORT_COVERAGE_REVIEW"): {
        "action_id": "act_002_escort",
        "insight_id": "ins_002",
        "type": "ESCORT_COVERAGE_REVIEW",
        "title": "Escort coverage gap -- night, female employees",
        "recipient": {"role": "vendor_account_manager", "name": "Sneha Mikhailov Travel & Meera Pavlov Travel"},
        "channel": "email",
        "subject": "Night escort coverage, female employees -- coverage gap, not a compliance finding",
        "body": (
            "This is a note on night-time escort coverage for female employees, framed as a coverage gap "
            "rather than a compliance breach -- we do not hold the underlying policy document, so we make "
            "no claim either way about it.\n\n"
            "Coverage for this segment currently stands at 60.8% across 81,174 legs scanned this period, "
            "leaving 31,838 legs without an escort. That coverage rate is roughly double the 20.2% "
            "baseline escort rate across all legs, so targeting toward this segment appears to be "
            "working; the gap is that it has plateaued short of full coverage rather than closed.\n\n"
            "Sneha Mikhailov Travel and Meera Pavlov Travel account for the largest shares of the "
            "uncovered legs, at 61.0% and 59.7% of their respective allocations. We are asking both "
            "vendors to review escort resourcing for night, female-employee legs, and are separately "
            "raising a resourcing request on our side to close the remaining gap.\n\n"
            "We would appreciate a response by the end of next week."
        ),
        "facts_cited": [
            {"label": "Coverage in this segment", "value": "60.8%", "source_field": "metric.value"},
            {"label": "Legs scanned in this segment", "value": "81,174", "source_field": "metric.n"},
            {"label": "Uncovered legs", "value": "31,838", "source_field": "impact.affected_trips"},
            {"label": "Baseline escort rate across all legs", "value": "20.2%",
             "source_field": "references[label=baseline escort rate across all legs].value"},
            {"label": "Vendor", "value": "Sneha Mikhailov Travel", "source_field": "attribution[dim=vendor_id].value"},
            {"label": "Sneha Mikhailov Travel share of uncovered legs", "value": "61.0% (14,620 legs)",
             "source_field": "attribution[dim=vendor_id]"},
            {"label": "Vendor", "value": "Meera Pavlov Travel", "source_field": "attribution[dim=vendor_id].value"},
            {"label": "Meera Pavlov Travel share of uncovered legs", "value": "59.7% (11,940 legs)",
             "source_field": "attribution[dim=vendor_id]"},
        ],
        "preview": {
            "what_changes": "Approving records the decision to an approval log; no note is actually sent to the vendors.",
            "reversible": True,
        },
        "rationale": (
            "Coverage has plateaued below full despite strong targeting, concentrated at two vendors -- "
            "close enough to name them and ask for a resourcing plan."
        ),
        "confidence": "high",
    },
    ("ins_003", "BILLING_RECONCILIATION"): {
        "action_id": "act_003_billing",
        "insight_id": "ins_003",
        "type": "BILLING_RECONCILIATION",
        "title": "Reconcile EV Contract billing -- 2,056 affected rows",
        "recipient": {"role": "finance_team", "name": "Finance team"},
        "channel": "email",
        "subject": "Billing reconciliation -- EV Contract, 2,056 rows",
        "body": (
            "This is a request to reconcile billing against actual figures before the next billing "
            "cycle.\n\n"
            "Of 25,351 rows scanned this period, 2,056 (8.11%) do not match the contracted expectation "
            "(electric). That represents a monthly billing exposure of ₹2.87M.\n\n"
            "We are unable to confirm from our side whether these rows reflect a genuine mismatch or a "
            "data- or contract-mapping issue -- we would ask finance to reconcile contract terms against "
            "actual figures for the affected rows before the next billing cycle closes.\n\n"
            "The affected row list is available on request. We would appreciate a response by the end of "
            "next week."
        ),
        "facts_cited": [
            {"label": "Rows scanned this period", "value": "25,351", "source_field": "metric.n"},
            {"label": "Rows affected", "value": "2,056 (8.11%)", "source_field": "impact.affected_trips"},
            {"label": "Monthly billing exposure", "value": "₹2.87M", "source_field": "impact.cost_inr_month"},
            {"label": "Contracted expectation", "value": "electric",
             "source_field": "references[label=expected fuel_type for EV contract].value"},
        ],
        "preview": {
            "what_changes": "Approving records the decision to an approval log; no note is actually sent to finance.",
            "reversible": True,
        },
        "rationale": (
            "A direct, quantifiable billing exposure with a small, enumerable set of affected rows -- "
            "reconciliation is mechanical, not investigative."
        ),
        "confidence": "high",
    },
}


@app.post("/internal/draft-action")
def draft_action(payload: dict) -> dict:
    insight = payload.get("insight") or {}
    action_type = payload.get("type")
    key = (insight.get("insight_id"), action_type)
    draft = ACTION_DRAFTS.get(key)
    if draft is None:
        raise HTTPException(status_code=400, detail=f"no mock draft for {key}")
    return draft


# Hardcoded response for POST /internal/evaluate-alerts -- what
# agent/app/detect/alert_router.py's evaluate() would return for exactly
# these three insights against agent/app/detect/alert_rules.yaml's five
# seed rules, precomputed by hand rather than imported (this script stays
# standalone -- no imports from agent/app, see the module docstring).
# `known_entities` from the request is intentionally ignored: whether a
# rescan re-fires r_new_bad_entity is not what the demo's "re-scan does not
# re-fire" claim is about (that's r_recon_critical's cooldown, which Java
# enforces regardless of what this endpoint returns) -- see
# job/ScanService for why that still holds even though this mock is static.
ALERT_CANDIDATES: list[dict] = [
    {"rule_id": "r_recon_critical", "insight_id": "ins_001", "persona": "ops", "urgency": "immediate",
     "channel": "in_app", "entity_dim": "fleet", "entity_value": "ALL", "cooldown_hours": 24},
    {"rule_id": "r_new_bad_entity", "insight_id": "ins_001", "persona": "ops", "urgency": "daily",
     "channel": "in_app", "entity_dim": "fleet", "entity_value": "ALL", "cooldown_hours": 24},
    {"rule_id": "r_safety_coverage", "insight_id": "ins_002", "persona": "strategic", "urgency": "daily",
     "channel": "in_app", "entity_dim": "segment", "entity_value": "night_female_escort", "cooldown_hours": 168},
    {"rule_id": "r_new_bad_entity", "insight_id": "ins_002", "persona": "ops", "urgency": "daily",
     "channel": "in_app", "entity_dim": "segment", "entity_value": "night_female_escort", "cooldown_hours": 24},
    {"rule_id": "r_billing_leak", "insight_id": "ins_003", "persona": "strategic", "urgency": "weekly",
     "channel": "email_digest", "entity_dim": "contract_type", "entity_value": "EV", "cooldown_hours": 168},
    {"rule_id": "r_new_bad_entity", "insight_id": "ins_003", "persona": "ops", "urgency": "daily",
     "channel": "in_app", "entity_dim": "contract_type", "entity_value": "EV", "cooldown_hours": 24},
]


@app.post("/internal/evaluate-alerts")
def evaluate_alerts(payload: dict) -> dict:
    insights = payload.get("insights") or []
    present_ids = {insight.get("insight_id") for insight in insights}
    ranked = sorted(
        (i for i in INSIGHTS.values() if i["insight_id"] in present_ids),
        key=lambda i: i["severity"],
        reverse=True,
    )
    candidates = [c for c in ALERT_CANDIDATES if c["insight_id"] in present_ids]
    return {"candidates": candidates, "ranked_insight_ids": [i["insight_id"] for i in ranked]}


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
