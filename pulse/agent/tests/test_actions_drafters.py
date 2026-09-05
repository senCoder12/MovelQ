from app.actions import drafters
from app.agent import validator

# Same figures as scripts/mock_agent.py's INSIGHTS -- kept inline here so
# these tests don't reach across the agent/scripts project boundary.
INS_001 = {
    "insight_id": "ins_001",
    "severity": 92,
    "metric": {"id": "delay_reconciliation_gap", "name": "Delay reconciliation gap", "value": 54.5,
               "unit": "%", "n": 215885, "window": "trailing_30d"},
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
    "trace": [],
    "narrative": {"headline": "117,605 trips arrived late while reporting zero delay", "body": "", "recommended_actions": []},
}

INS_002 = {
    "insight_id": "ins_002",
    "severity": 71,
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
    "trace": [],
    "narrative": {"headline": "Night escort coverage for female employees stops at 61%", "body": "", "recommended_actions": []},
}

INS_003 = {
    "insight_id": "ins_003",
    "severity": 58,
    "metric": {"id": "ev_contract_mismatch_rate", "name": "EV-contract trips run on non-EV fuel", "value": 8.11,
               "unit": "%", "n": 25351, "window": "trailing_30d"},
    "entity": {"dim": "contract_type", "id": "EV", "name": "EV Contract"},
    "references": [{"type": "computed", "label": "expected fuel_type for EV contract", "value": "electric", "unit": "text"}],
    "attribution": [],
    "controls": [],
    "coincident_events": [],
    "impact": {"affected_trips": 2056, "cost_inr_month": 2870000.0},
    "data_quality": {"excluded_pct": 0.0, "confidence": "medium"},
    "trace": [],
    "narrative": {"headline": "2,056 trips billed on EV contracts ran on petrol or diesel", "body": "", "recommended_actions": []},
}


def test_applicable_action_types_delay_reconciliation():
    assert drafters.applicable_action_types(INS_001) == ["VENDOR_ESCALATION", "SYSTEM_AUDIT_REQUEST"]


def test_applicable_action_types_escort_coverage_is_exclusive():
    # Vendor-attributed too, but must not also surface VENDOR_ESCALATION --
    # see module docstring.
    assert drafters.applicable_action_types(INS_002) == ["ESCORT_COVERAGE_REVIEW"]


def test_applicable_action_types_billing():
    assert drafters.applicable_action_types(INS_003) == ["BILLING_RECONCILIATION"]


def test_applicable_action_types_no_vendor_no_special_metric():
    bare = {"metric": {"id": "something_else"}, "attribution": []}
    assert drafters.applicable_action_types(bare) == []


def test_draft_action_rejects_inapplicable_type():
    import pytest

    with pytest.raises(ValueError):
        drafters.draft_action(INS_002, "VENDOR_ESCALATION")


def test_draft_action_rejects_unknown_type():
    import pytest

    with pytest.raises(ValueError):
        drafters.draft_action(INS_001, "NOT_A_TYPE")


def _assert_well_formed(draft: dict, insight_id: str, action_type: str) -> None:
    assert draft["action_id"].startswith("act_")
    assert draft["insight_id"] == insight_id
    assert draft["type"] == action_type
    assert draft["title"]
    assert draft["recipient"]["name"]
    assert draft["subject"]
    assert draft["body"]
    assert draft["facts_cited"]
    for fact in draft["facts_cited"]:
        assert fact["label"] and fact["value"] and fact["source_field"]
    assert draft["preview"]["reversible"] is True
    assert draft["rationale"]
    assert draft["confidence"] in ("high", "medium", "low")


def test_vendor_escalation_draft_is_grounded_and_well_formed():
    # No LLM_API_KEY in the test environment -- exercises the template fallback.
    draft = drafters.draft_action(INS_001, "VENDOR_ESCALATION")
    _assert_well_formed(draft, "ins_001", "VENDOR_ESCALATION")
    assert draft["confidence"] == "low"
    assert "Vikram Mikhailov Travel" in draft["body"]
    assert draft["recipient"]["role"] == "vendor_account_manager"
    result = validator.validate_action(INS_001, draft["subject"], draft["body"])
    assert result.ok, result.ungrounded
    # No sender-set deadline: a calendar date would also fail grounding.
    assert "by the end of next week" in draft["body"]


def test_system_audit_request_states_hypothesis_not_conclusion():
    draft = drafters.draft_action(INS_001, "SYSTEM_AUDIT_REQUEST")
    _assert_well_formed(draft, "ins_001", "SYSTEM_AUDIT_REQUEST")
    assert "hypothesis" in draft["body"].lower()
    assert "2" in " ".join(f["value"] for f in draft["facts_cited"])
    result = validator.validate_action(INS_001, draft["subject"], draft["body"])
    assert result.ok, result.ungrounded


def test_escort_coverage_review_never_says_non_compliance():
    draft = drafters.draft_action(INS_002, "ESCORT_COVERAGE_REVIEW")
    _assert_well_formed(draft, "ins_002", "ESCORT_COVERAGE_REVIEW")
    assert "non-compliance" not in draft["body"].lower()
    assert "violation" not in draft["body"].lower()
    assert "coverage gap" in draft["body"].lower()
    assert "sneha mikhailov travel" in draft["body"].lower()
    result = validator.validate_action(INS_002, draft["subject"], draft["body"])
    assert result.ok, result.ungrounded


def test_billing_reconciliation_lists_affected_rows():
    draft = drafters.draft_action(INS_003, "BILLING_RECONCILIATION")
    _assert_well_formed(draft, "ins_003", "BILLING_RECONCILIATION")
    assert "2,056" in draft["body"]
    assert draft["recipient"]["role"] == "finance_team"
    result = validator.validate_action(INS_003, draft["subject"], draft["body"])
    assert result.ok, result.ungrounded
