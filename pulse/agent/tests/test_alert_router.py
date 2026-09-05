from app.detect import alert_router


def _insight(insight_id, metric_id, severity, value=50.0, n=10000, entity_id="ALL", entity_dim="fleet",
             references=None):
    return {
        "insight_id": insight_id,
        "severity": severity,
        "metric": {"id": metric_id, "name": metric_id, "value": value, "unit": "%", "n": n, "window": "trailing_30d"},
        "entity": {"dim": entity_dim, "id": entity_id, "name": entity_id},
        "references": references or [],
        "attribution": [],
        "controls": [],
        "coincident_events": [],
        "impact": {},
        "data_quality": {"excluded_pct": 0.0, "confidence": "high"},
        "trace": [],
        "narrative": {"headline": insight_id, "body": "", "recommended_actions": []},
    }


RULES = [
    {"id": "r_sev", "metric_id": "delay_reconciliation_gap", "condition": "severity_gte", "threshold": 85,
     "persona": "ops", "urgency": "immediate", "channel": "in_app", "cooldown_hours": 24, "min_sample": 1000},
    {"id": "r_delta", "metric_id": "escort_coverage_night_female", "condition": "delta_pp_gte", "threshold": 10,
     "persona": "strategic", "urgency": "daily", "channel": "in_app", "cooldown_hours": 168, "min_sample": 500},
    {"id": "r_sla", "metric_id": "*", "condition": "sla_breach", "threshold": 0, "persona": "ops",
     "urgency": "immediate", "channel": "in_app", "cooldown_hours": 12, "min_sample": 0},
    {"id": "r_new", "metric_id": "*", "condition": "new_entity", "threshold": 0, "persona": "ops",
     "urgency": "daily", "channel": "in_app", "cooldown_hours": 24, "min_sample": 0},
]


def test_rank_and_dedupe_keeps_the_higher_severity_duplicate():
    weak = _insight("ins_a", "delay_reconciliation_gap", severity=40)
    strong = _insight("ins_b", "delay_reconciliation_gap", severity=92)
    ranked = alert_router.rank_and_dedupe([weak, strong])
    assert [i["insight_id"] for i in ranked] == ["ins_b"]


def test_rank_and_dedupe_keeps_distinct_entities_under_the_same_metric():
    vendor_a = _insight("ins_a", "ev_contract_mismatch_rate", severity=60, entity_id="vendor-a")
    vendor_b = _insight("ins_b", "ev_contract_mismatch_rate", severity=55, entity_id="vendor-b")
    ranked = alert_router.rank_and_dedupe([vendor_a, vendor_b])
    assert {i["insight_id"] for i in ranked} == {"ins_a", "ins_b"}


def test_rank_and_dedupe_sorts_by_severity_descending():
    low = _insight("ins_low", "metric_a", severity=20, entity_id="x")
    high = _insight("ins_high", "metric_b", severity=90, entity_id="y")
    ranked = alert_router.rank_and_dedupe([low, high])
    assert [i["insight_id"] for i in ranked] == ["ins_high", "ins_low"]


def test_severity_gte_fires_on_the_recon_insight():
    insight = _insight("ins_001", "delay_reconciliation_gap", severity=92, n=215885)
    candidates = alert_router.evaluate([insight], rules=RULES)
    rule_ids = {c["rule_id"] for c in candidates}
    assert "r_sev" in rule_ids


def test_severity_gte_respects_min_sample():
    insight = _insight("ins_001", "delay_reconciliation_gap", severity=92, n=10)
    candidates = alert_router.evaluate([insight], rules=RULES)
    assert all(c["rule_id"] != "r_sev" for c in candidates)


def test_delta_pp_gte_fires_on_a_coverage_shortfall():
    insight = _insight("ins_002", "escort_coverage_night_female", severity=71, value=60.8, n=81174)
    candidates = alert_router.evaluate([insight], rules=RULES)
    matching = [c for c in candidates if c["rule_id"] == "r_delta"]
    assert len(matching) == 1
    assert matching[0]["persona"] == "strategic"


def test_delta_pp_gte_does_not_fire_within_ten_points_of_full_coverage():
    insight = _insight("ins_002", "escort_coverage_night_female", severity=71, value=95.0, n=81174)
    candidates = alert_router.evaluate([insight], rules=RULES)
    assert all(c["rule_id"] != "r_delta" for c in candidates)


def test_sla_breach_requires_an_sla_typed_reference():
    without_sla = _insight("ins_x", "any_metric", severity=10)
    with_sla = _insight("ins_y", "any_metric", severity=10,
                         references=[{"type": "sla", "label": "contracted max", "value": 15, "unit": "minutes"}])
    assert all(c["rule_id"] != "r_sla" for c in alert_router.evaluate([without_sla], rules=RULES))
    assert any(c["rule_id"] == "r_sla" for c in alert_router.evaluate([with_sla], rules=RULES))


def test_new_entity_fires_only_for_unseen_entities():
    seen = _insight("ins_seen", "any_metric", severity=10, entity_id="vendor-a")
    unseen = _insight("ins_unseen", "any_metric", severity=10, entity_id="vendor-b")
    known = {("fleet", "vendor-a")}
    candidates = alert_router.evaluate([seen, unseen], known_entities=known, rules=RULES)
    new_hits = {c["insight_id"] for c in candidates if c["rule_id"] == "r_new"}
    assert new_hits == {"ins_unseen"}


def test_candidate_carries_entity_and_cooldown_for_java_to_apply():
    insight = _insight("ins_001", "delay_reconciliation_gap", severity=92, n=215885, entity_id="ALL")
    candidates = alert_router.evaluate([insight], known_entities={("fleet", "ALL")}, rules=RULES)
    match = next(c for c in candidates if c["rule_id"] == "r_sev")
    assert match["entity_dim"] == "fleet"
    assert match["entity_value"] == "ALL"
    assert match["cooldown_hours"] == 24


def test_seed_rules_file_loads_and_fires_on_confirmed_findings():
    rules = alert_router.load_rules()
    assert {r["id"] for r in rules} == {
        "r_recon_critical", "r_safety_coverage", "r_billing_leak", "r_new_bad_entity", "r_sla_any",
    }

    ins_001 = _insight("ins_001", "delay_reconciliation_gap", severity=92, n=215885, entity_id="ALL", entity_dim="fleet")
    ins_002 = _insight("ins_002", "escort_coverage_night_female", severity=71, value=60.8, n=81174,
                        entity_id="night_female_escort", entity_dim="segment")
    ins_003 = _insight("ins_003", "ev_contract_mismatch_rate", severity=58, value=8.11, n=25351,
                        entity_id="EV", entity_dim="contract_type")

    candidates = alert_router.evaluate([ins_001, ins_002, ins_003], rules=rules)
    fired_by_insight = {}
    for c in candidates:
        fired_by_insight.setdefault(c["insight_id"], set()).add(c["rule_id"])

    assert "r_recon_critical" in fired_by_insight["ins_001"]
    assert "r_safety_coverage" in fired_by_insight["ins_002"]
    assert "r_billing_leak" in fired_by_insight["ins_003"]
    # Every insight is a first-ever entity on an empty history.
    assert fired_by_insight["ins_001"] >= {"r_recon_critical", "r_new_bad_entity"}
