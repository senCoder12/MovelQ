"""Detection tests.

These run against the real warehouse: the whole point of this layer is what it
concludes from actual data, and a fixture small enough to hand-write would not
exercise the aggregation, the attribution ranking, or the guards that were added
because real data broke them. Skipped when the warehouse is absent.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.config import get_settings
from app.detect import signals
from app.metrics import compiler

REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_PATH = REPO_ROOT / "pulse" / "contracts" / "insight.schema.json"

pytestmark = pytest.mark.skipif(
    not get_settings().duckdb_path.exists(), reason="warehouse not built"
)


@pytest.fixture(scope="module")
def tenants() -> list[str]:
    found = signals.tenants()
    if not found:
        pytest.skip("warehouse has no tenants")
    return found


def test_every_packet_matches_the_contract(tenants):
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA_PATH.read_text())
    checked = 0
    for tenant_id in tenants:
        for insight in signals.detect_tenant(tenant_id):
            jsonschema.validate(insight, schema)
            checked += 1
    assert checked > 0, "detection produced nothing to validate"


def test_insights_are_ordered_worst_first(tenants):
    severities = [insight["severity"] for insight in signals.detect_tenant(tenants[0])]
    assert severities == sorted(severities, reverse=True)


def test_detection_is_tenant_scoped(tenants):
    for tenant_id in tenants:
        for insight in signals.detect_tenant(tenant_id):
            assert insight["entity"]["id"] == tenant_id


def test_reported_rate_is_reproducible_from_its_own_trace(tenants):
    """The trace has to reconstruct the headline number, or it is decoration."""
    for tenant_id in tenants:
        for insight in signals.detect_tenant(tenant_id):
            overall = next(
                entry for entry in insight["trace"] if entry["query_id"].endswith("__overall")
            )
            recomputed = 100.0 * overall["numerator"] / overall["denominator"]
            assert recomputed == pytest.approx(insight["metric"]["value"], abs=0.01)
            assert overall["denominator"] == insight["metric"]["n"]


def test_only_breaching_metrics_are_reported(tenants):
    for tenant_id in tenants:
        for insight in signals.detect_tenant(tenant_id):
            metric = compiler.get_metric(insight["insight_id"])
            warn = metric["targets"]["warn"]
            value = insight["metric"]["value"] / 100.0
            if metric["direction"] == "higher_better":
                assert value < warn
            else:
                assert value > warn
            assert 50 <= insight["severity"] <= 100


def test_attribution_never_claims_more_than_all_of_it(tenants):
    for tenant_id in tenants:
        for insight in signals.detect_tenant(tenant_id):
            for entry in insight["attribution"]:
                assert 0 <= entry["contribution_pct"] <= 100
                assert entry["n"] > 0


def test_escort_coverage_is_not_inverted_by_its_exclusions():
    """Regression: excluding DELAY_UNREPORTED and ROSTER_OVERCOUNT -- both confounded
    with escorted legs -- once dragged reported coverage from 74.7% to 3.1%."""
    metric = compiler.get_metric("escort_coverage_night_female")
    assert "DELAY_UNREPORTED" not in metric["exclude_flags"]
    assert "ROSTER_OVERCOUNT" not in metric["exclude_flags"]

    for tenant_id in signals.tenants():
        insight = signals.detect_metric(tenant_id, metric)
        if insight is not None:
            assert insight["metric"]["value"] > 10.0, (
                "coverage in low single digits means the exclusions are removing "
                "escorted legs, not bad data"
            )


def test_unpopulated_source_column_is_not_reported_as_a_finding():
    """Regression: billed_km is empty for some tenants, which read as '97.8% of km
    unbilled, INR 101M exposed' -- a missing column, not a billing leak."""
    metric = compiler.get_metric("unbilled_km_rate")
    assert metric.get("requires_populated"), "the completeness guard has been removed"
    for tenant_id in signals.tenants():
        insight = signals.detect_metric(tenant_id, metric)
        assert insight is None or insight["metric"]["value"] < 90.0


def test_window_is_derived_per_table_not_from_fact_trip():
    """Regression: billing is keyed on fortnightly cycles from May while trips are
    July-only, so one shared window silently hid every billing finding."""
    billing = signals.window_for("orbit", "fact_trip_billing", "cycle_start")
    trips = signals.window_for("orbit", "fact_trip", "trip_date")
    assert billing is not None and trips is not None
    assert billing != trips
