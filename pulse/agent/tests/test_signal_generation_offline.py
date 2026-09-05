"""Layer 2 -- runtime interception.

Layer 1 proves the signal path cannot *import* its way to a model. This proves
it does not get there at runtime either: the model client and the HTTP
transports under it are replaced with something that raises, and the whole
signal path is then run against the real warehouse.

Two halves, and the second is the one that matters:

  * every stage completes and produces non-empty output with no model available
  * the figures it produces are the confirmed ones

Absence of failure is cheap -- a pipeline that returned empty lists would pass
the first half. The second half is what proves the system finds the headline
finding on its own.
"""

from __future__ import annotations

import pytest

from app.detect import signals
from app.metrics import compiler

TENANTS = ("catalyst", "vanta", "orbit", "pinnacle")

#: The tenant the ':16' shift-suffix finding actually belongs to. All 29,854
#: ':16' trips in the warehouse are vanta's; catalyst has none.
SUFFIX_TENANT = "vanta"


class LLMCalledError(AssertionError):
    """Raised in place of any model call. An AssertionError subclass so a stage
    that swallows RuntimeError -- both real call sites do, to fall back to a
    template -- cannot quietly absorb it and let the test pass."""


@pytest.fixture
def no_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make every route to a model raise.

    Patched at three depths, because patching only the top one proves only that
    the top one was not called:

      1. ``app.llm.client.complete`` -- the single in-repo model entry point
      2. ``google.genai.Client`` -- the SDK it constructs, deferred inside the
         function body, so a caller bypassing ``complete`` is still caught
      3. ``httpx.Client.send`` / ``AsyncClient.send`` -- the transport the SDK
         rides on. ``send`` rather than ``post``: the SDK builds requests and
         dispatches them through ``send``, so patching ``post`` alone would miss
         the call entirely.
    """
    def boom(*args: object, **kwargs: object) -> object:
        raise LLMCalledError("LLM called during signal generation")

    import httpx

    from app.llm import client as llm_client

    monkeypatch.setattr(llm_client, "complete", boom)
    monkeypatch.setattr(httpx.Client, "send", boom)
    monkeypatch.setattr(httpx.AsyncClient, "send", boom)
    monkeypatch.setattr(httpx.Client, "post", boom)
    monkeypatch.setattr(httpx.AsyncClient, "post", boom)

    try:
        from google import genai
    except ImportError:  # SDK not installed in this checkout
        return
    monkeypatch.setattr(genai, "Client", boom)


def _registry_metrics() -> list[dict]:
    return compiler.load_registry()["metrics"]


# --------------------------------------------------------------------------
# Stage 1-5: every stage completes, offline, with non-empty output
# --------------------------------------------------------------------------


def test_stage1_metric_compilation_offline(no_llm: None) -> None:
    """All 10 registry metrics compile and run against the warehouse."""
    metrics = _registry_metrics()
    assert len(metrics) == 10, f"registry declares {len(metrics)} metrics, expected 10"

    compiled = 0
    for metric in metrics:
        window = signals.window_for(
            SUFFIX_TENANT, metric["table"], compiler.date_column(metric)
        )
        if window is None:
            continue
        frame = compiler.run_metric(
            SUFFIX_TENANT, metric["id"], "tenant_id", window[0], window[1]
        )
        assert not frame.empty, f"{metric['id']} compiled to an empty series"
        compiled += 1
    assert compiled == 10, f"only {compiled}/10 metrics produced a series"


def test_stage2_detection_across_every_slice_dimension_offline(no_llm: None) -> None:
    """Every dimension each metric declares in slice_by is actually queryable.

    A slice that silently returns nothing is a dimension the system claims to
    attribute across but cannot, which is how an attribution list ends up
    quietly shorter than the registry implies.
    """
    empty: list[str] = []
    for metric in _registry_metrics():
        window = signals.window_for(
            SUFFIX_TENANT, metric["table"], compiler.date_column(metric)
        )
        if window is None:
            continue
        for dim in metric["slice_by"]:
            frame = compiler.run_metric(
                SUFFIX_TENANT, metric["id"], dim, window[0], window[1]
            )
            if frame.empty:
                empty.append(f"{metric['id']}.{dim}")
    assert not empty, f"slice dimensions produced no rows: {empty}"


def test_stage3_attribution_offline(no_llm: None) -> None:
    """Attribution runs and names slices, for every tenant that breaches."""
    for tenant in TENANTS:
        insights = signals.detect_tenant(tenant)
        assert insights, f"{tenant}: detection produced no insights"
        attributed = [i for i in insights if i["attribution"]]
        assert attributed, f"{tenant}: no insight carried any attribution"
        for insight in attributed:
            for entry in insight["attribution"]:
                assert entry["dim"] and entry["value"]
                assert 0 < entry["contribution_pct"] <= 100
                assert entry["n"] > 0


def test_stage4_severity_and_dedupe_offline(no_llm: None) -> None:
    """Severity is scored and the output carries one row per metric, ranked."""
    insights = signals.detect_tenant(SUFFIX_TENANT)
    severities = [i["severity"] for i in insights]

    assert all(50 <= s <= 100 for s in severities), (
        f"a breach scored outside the 50-100 band: {severities}"
    )
    assert severities == sorted(severities, reverse=True), (
        f"output is not ranked by severity: {severities}"
    )
    ids = [i["insight_id"] for i in insights]
    assert len(ids) == len(set(ids)), f"duplicate insight_ids survived dedupe: {ids}"


def test_stage5_alert_rule_evaluation_offline(no_llm: None) -> None:
    """Alert rules are evaluated over the ranked output with no model in the loop.

    There is no alerting subsystem in this tree -- no rule definitions, no
    evaluator, no firing record. Grep for `alert` across agent and backend
    returns only frontend presentation strings. The claim "alert evaluation
    produces every signal with zero model calls" has nothing to evaluate, so it
    is neither true nor false; it is untested.
    """
    pytest.fail(
        "no alert rule engine exists (no rule definitions, evaluator, or firing "
        "record in agent/ or backend/); alert evaluation cannot be exercised"
    )


# --------------------------------------------------------------------------
# Correctness: the confirmed figures, reproduced with no model available
# --------------------------------------------------------------------------


def _suffix_totals(tenant: str = SUFFIX_TENANT):
    """The delay-gap rate per shift_suffix, straight off the compiler."""
    window = signals.window_for(tenant, "fact_trip", "trip_date")
    assert window is not None
    totals = signals._totals_by_dim(
        tenant, "delay_reconciliation_gap", "shift_suffix", window[0], window[1]
    )
    return totals.sort_values("value", ascending=False)


def test_figure_delay_gap_on_suffix_16(no_llm: None) -> None:
    """delay_reconciliation_gap on shift_suffix ':16' = 58.4% (+/- 0.1pp)."""
    totals = _suffix_totals()
    row = totals[totals["dim_value"] == ":16"]
    assert not row.empty, "':16' produced no slice"
    actual = float(row.iloc[0]["value"]) * 100
    assert abs(actual - 58.4) <= 0.1, f"':16' delay gap is {actual:.2f}%, claimed 58.4%"


def test_figure_n_for_suffix_16(no_llm: None) -> None:
    """n for the ':16' slice = 29,854."""
    totals = _suffix_totals()
    row = totals[totals["dim_value"] == ":16"]
    assert not row.empty, "':16' produced no slice"
    assert int(row.iloc[0]["denominator"]) == 29_854, (
        f"':16' n is {int(row.iloc[0]['denominator']):,}, claimed 29,854"
    )


def test_figure_next_worst_suffix(no_llm: None) -> None:
    """Next-worst suffix = 38.2%."""
    totals = _suffix_totals()
    runner_up = float(totals.iloc[1]["value"]) * 100
    assert abs(runner_up - 38.2) <= 0.1, (
        f"next-worst suffix ({totals.iloc[1]['dim_value']}) is {runner_up:.2f}%, claimed 38.2%"
    )


def test_figure_fleet_delay_unreported_trips(no_llm: None) -> None:
    """Fleet-wide DELAY_UNREPORTED trips = 117,605."""
    total = sum(
        signals._adverse(
            signals._overall(
                tenant,
                "delay_reconciliation_gap",
                *signals.window_for(tenant, "fact_trip", "trip_date"),
            ),
            "lower_better",
        )
        for tenant in TENANTS
    )
    assert int(total) == 117_605, (
        f"fleet-wide DELAY_UNREPORTED trips = {int(total):,}, claimed 117,605"
    )


def test_figure_female_night_legs_without_escort(no_llm: None) -> None:
    """Female night legs without escort = 31,838 of 81,174, fleet-wide."""
    uncovered = 0.0
    total = 0.0
    for tenant in TENANTS:
        window = signals.window_for(tenant, "fact_trip_employee", "trip_date")
        if window is None:
            continue
        overall = signals._overall(tenant, "escort_coverage_night_female", *window)
        if overall is None:
            continue
        uncovered += signals._adverse(overall, "higher_better")
        total += overall.denominator
    assert (int(uncovered), int(total)) == (31_838, 81_174), (
        f"female night legs without escort = {int(uncovered):,} of {int(total):,}, "
        "claimed 31,838 of 81,174"
    )


def test_figure_fuel_contract_mismatch_rows(no_llm: None) -> None:
    """FUEL_CONTRACT_MISMATCH rows = 2,056, fleet-wide."""
    rows = 0.0
    for tenant in TENANTS:
        window = signals.window_for(tenant, "fact_trip_billing", "cycle_start")
        if window is None:
            continue
        overall = signals._overall(tenant, "ev_contract_mismatch_rate", *window)
        if overall is None:
            continue
        rows += signals._adverse(overall, "lower_better")
    assert int(rows) == 2_056, f"EV/fuel contract mismatch rows = {int(rows):,}, claimed 2,056"


def test_suffix_16_signal_ranks_first(no_llm: None) -> None:
    """The ':16' signal ranks FIRST by severity.

    This is the assertion the whole layer exists for: with no model available,
    the system's own ranking has to surface the headline finding at the top.
    """
    insights = signals.detect_tenant(SUFFIX_TENANT)
    assert insights, "detection produced nothing"
    top = insights[0]
    top_attribution = top["attribution"][0] if top["attribution"] else None
    assert top["insight_id"] == "delay_reconciliation_gap" and (
        top_attribution is not None
        and top_attribution["dim"] == "shift_suffix"
        and top_attribution["value"] == ":16"
    ), (
        "the ':16' signal does not rank first. Top insight is "
        f"{top['insight_id']!r} (severity {top['severity']}) attributed to "
        f"{top_attribution['dim'] + '=' + top_attribution['value'] if top_attribution else 'nothing'}. "
        "Full ranking: "
        + ", ".join(f"{i['insight_id']}({i['severity']})" for i in insights)
    )
