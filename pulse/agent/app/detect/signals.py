"""Turn metric series into insights.

This is the step between "the warehouse can compute a number" and "there is
something worth telling someone about". For one tenant and one window it walks
the metric registry and, for each metric that breaches its declared target,
assembles an InsightPacket matching contracts/insight.schema.json:

  * the headline number, aggregated over the whole window
  * who it is concentrated in (attribution across the metric's declared slices)
  * whether that concentration explains it away (controls, by leave-one-out)
  * what it costs (impact, from the registry's declared impact expressions)
  * how much data was thrown away to get it (data quality)
  * the queries that produced all of the above (trace)

Nothing here invents a number. Every figure in the narrative is one that also
appears in a structured field, which is the same rule app/agent/validator.py
enforces for the leadership pack.

Scope: metrics whose unit is a rate or ratio, and which declare a warn target.
Those aggregate correctly over periods by summing numerator and denominator.
p90_arrival_delay_min deliberately does not -- a weighted mean of daily p90s is
not the window's p90 -- and cost_per_employee_trip has no target to breach.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from app import db
from app.ingest import quality
from app.metrics import compiler

#: Metric units this detector can aggregate over a window without lying.
AGGREGATABLE_UNITS = frozenset({"rate", "ratio"})

#: Slices reported as attribution, most concentrated first.
MAX_ATTRIBUTION = 3

#: Dimensions tested as controls.
MAX_CONTROLS = 2

#: A slice must carry at least this share of the adverse rows to be worth naming.
MIN_CONTRIBUTION_PCT = 5.0


@dataclass(frozen=True)
class Totals:
    """Numerator, denominator and rate for one slice over the whole window."""

    numerator: float
    denominator: float

    @property
    def value(self) -> float | None:
        return self.numerator / self.denominator if self.denominator else None


def _totals_by_dim(
    tenant_id: str, metric_id: str, dim: str, start: str, end: str, grain: str = "day"
) -> pd.DataFrame:
    """Aggregate a metric's per-period series up to one row per slice value.

    The compiler returns a rate per (slice, period). Summing ``value * n`` back
    into a numerator and ``n`` into a denominator recovers the window total,
    which is exact for rate and ratio metrics. Periods the compiler nulled for
    falling under min_sample are dropped and counted, not silently treated as
    zero.
    """
    frame = compiler.run_metric(tenant_id, metric_id, dim, start, end, grain=grain)
    usable = frame.dropna(subset=["value"])
    if usable.empty:
        return pd.DataFrame(columns=["dim_value", "numerator", "denominator", "value"])

    usable = usable.assign(numerator=usable["value"] * usable["n"])
    totals = (
        usable.groupby("dim_value", dropna=True)
        .agg(numerator=("numerator", "sum"), denominator=("n", "sum"))
        .reset_index()
    )
    totals["value"] = totals["numerator"] / totals["denominator"].replace(0, pd.NA)
    return totals.dropna(subset=["value"])


def _overall(tenant_id: str, metric_id: str, start: str, end: str) -> Totals | None:
    """The whole-tenant figure. Every metric declares tenant_id as a slice, so
    this is the compiler's own output rather than a second, differently-written
    query that could drift from it."""
    totals = _totals_by_dim(tenant_id, metric_id, "tenant_id", start, end)
    if totals.empty:
        return None
    return Totals(float(totals["numerator"].sum()), float(totals["denominator"].sum()))


def _adverse(totals: Totals, direction: str) -> float:
    """The count the metric is actually complaining about.

    For a lower_better metric that is the numerator: late trips, mismatched
    contracts. For a higher_better one it is the shortfall -- uncovered legs,
    not covered ones -- because "31,838 legs uncovered" is the number a reader
    can act on, and it is what impact.affected_trips has to mean for the
    attribution percentages to add up.
    """
    if direction == "higher_better":
        return max(0.0, totals.denominator - totals.numerator)
    return totals.numerator


def _breaches(value: float, threshold: float, direction: str) -> bool:
    return value < threshold if direction == "higher_better" else value > threshold


def _breach_progress(value: float, warn: float, critical: float, direction: str) -> float:
    """How far past the warn target, measured in warn-to-critical distances.

    0 at warn, 1 at critical, and it keeps counting past that. Returned unclamped
    so the caller can decide where to stop.
    """
    span = abs(critical - warn)
    if span == 0:
        return 1.0
    distance = (warn - value) if direction == "higher_better" else (value - warn)
    return distance / span


def _severity(value: float, warn: float, critical: float, direction: str) -> int:
    """0-100, and only ever called for a metric already past its warn target.

    Sits at 50 on the warn line, 75 at critical, and reaches 100 at twice the
    warn-to-critical distance beyond warn. A breach is never scored below 50 --
    the decision that it is worth surfacing has already been made -- and the
    scale above that is a stated function of how far past target it is, not a
    judgement call.
    """
    progress = max(0.0, min(_breach_progress(value, warn, critical, direction), 2.0))
    return int(round(50 + 25 * progress))


def _attribution(
    tenant_id: str,
    metric: dict[str, Any],
    start: str,
    end: str,
    overall: Totals,
    direction: str,
) -> tuple[list[dict[str, Any]], dict[str, pd.DataFrame]]:
    """Which slice values carry the adverse rows.

    contribution_pct is a slice's share of the tenant's adverse count, not its
    own rate -- a vendor with a terrible rate on 40 trips has not caused the
    problem, and saying otherwise sends someone to the wrong meeting.
    """
    total_adverse = _adverse(overall, direction)
    slices_by_dim: dict[str, pd.DataFrame] = {}
    candidates: list[dict[str, Any]] = []

    for dim in metric["slice_by"]:
        if dim == "tenant_id":
            continue
        totals = _totals_by_dim(tenant_id, metric["id"], dim, start, end)
        if totals.empty:
            continue
        slices_by_dim[dim] = totals
        if total_adverse <= 0:
            continue
        for row in totals.itertuples():
            adverse = _adverse(Totals(float(row.numerator), float(row.denominator)), direction)
            contribution = 100.0 * adverse / total_adverse
            if contribution < MIN_CONTRIBUTION_PCT:
                continue
            candidates.append(
                {
                    "dim": dim,
                    "value": str(row.dim_value),
                    "contribution_pct": round(min(contribution, 100.0), 1),
                    "n": int(row.denominator),
                }
            )

    candidates.sort(key=lambda item: item["contribution_pct"], reverse=True)
    return candidates[:MAX_ATTRIBUTION], slices_by_dim


def _controls(
    metric: dict[str, Any],
    slices_by_dim: dict[str, pd.DataFrame],
    overall: Totals,
    direction: str,
    warn: float,
    skip_dim: str | None,
) -> list[dict[str, Any]]:
    """Does the breach survive removing the worst offender on each dimension?

    Leave-one-out: drop the single slice value carrying the most adverse rows,
    recompute the rate on what is left, and check whether it still breaches. If
    it does, the problem is not one bad vendor or one bad site -- which is the
    difference between an insight and a complaint.

    gap_pp is the remaining distance past target in percentage points, signed so
    that positive always means "still the wrong side of the line".
    """
    controls: list[dict[str, Any]] = []
    for dim, totals in slices_by_dim.items():
        if dim == skip_dim or len(totals) < 2:
            continue
        adverse = totals.apply(
            lambda row: _adverse(Totals(float(row["numerator"]), float(row["denominator"])), direction),
            axis=1,
        )
        worst = totals.loc[adverse.idxmax()]
        remaining = Totals(
            overall.numerator - float(worst["numerator"]),
            overall.denominator - float(worst["denominator"]),
        )
        if remaining.denominator <= 0 or remaining.value is None:
            continue
        gap = (warn - remaining.value) if direction == "higher_better" else (remaining.value - warn)
        controls.append(
            {
                "control": dim,
                "gap_pp": round(gap * 100, 1),
                "survives": bool(_breaches(remaining.value, warn, direction)),
            }
        )
        if len(controls) >= MAX_CONTROLS:
            break
    return controls


def _impact(
    tenant_id: str, metric: dict[str, Any], start: str, end: str, adverse: float
) -> dict[str, Any]:
    """affected_trips always; money and minutes only where the registry declares
    an expression for them. An impact figure nobody defined is not estimated."""
    impact: dict[str, Any] = {"affected_trips": int(round(adverse))}
    declared = metric.get("impact") or {}
    for field in ("cost_inr_month", "late_minutes_total"):
        expression = declared.get(field)
        if not expression:
            continue
        excluded_mask = quality.mask_from_names(metric.get("exclude_flags", []))
        date_col = compiler.date_column(metric)
        sql = (
            f"SELECT {expression} AS total FROM {metric['table']} "
            f"WHERE tenant_id = ? AND {date_col} BETWEEN ? AND ? "
            f"AND (dq_flags & {excluded_mask}) = 0"
        )
        row = db.fetch_one(tenant_id, sql, [start, end])
        if row and row[0] is not None:
            impact[field] = round(float(row[0]), 2)
    return impact


def _data_quality(tenant_id: str, metric: dict[str, Any], start: str, end: str) -> dict[str, Any]:
    """What share of the tenant's rows this metric threw away, and how much that
    should temper the reading."""
    excluded_mask = quality.mask_from_names(metric.get("exclude_flags", []))
    date_col = compiler.date_column(metric)
    sql = (
        "SELECT COUNT(*) AS total, "
        f"COUNT(*) FILTER (WHERE (dq_flags & {excluded_mask}) <> 0) AS excluded "
        f"FROM {metric['table']} WHERE tenant_id = ? AND {date_col} BETWEEN ? AND ?"
    )
    row = db.fetch_one(tenant_id, sql, [start, end])
    total, excluded = (int(row[0]), int(row[1])) if row else (0, 0)
    excluded_pct = round(100.0 * excluded / total, 2) if total else 0.0
    if excluded_pct < 2:
        confidence = "high"
    elif excluded_pct < 10:
        confidence = "medium"
    else:
        confidence = "low"
    return {"excluded_pct": excluded_pct, "confidence": confidence}


def _references(
    metric: dict[str, Any],
    warn: float,
    overall: Totals,
    attribution: list[dict[str, Any]],
    slices_by_dim: dict[str, pd.DataFrame],
    direction: str,
) -> list[dict[str, Any]]:
    references: list[dict[str, Any]] = [
        {
            "type": "sla",
            "label": f"target for {metric['id']}",
            "value": round(warn * 100, 2),
            "unit": "percent",
        },
        {
            "type": "computed",
            "label": "rows evaluated in window",
            "value": int(overall.denominator),
            "unit": "count",
        },
    ]
    if attribution:
        top = attribution[0]
        totals = slices_by_dim.get(top["dim"])
        if totals is not None and len(totals) > 1:
            ranked = totals.assign(
                adverse=totals.apply(
                    lambda row: _adverse(
                        Totals(float(row["numerator"]), float(row["denominator"])), direction
                    ),
                    axis=1,
                )
            ).sort_values("adverse", ascending=False)
            if len(ranked) > 1:
                runner_up = ranked.iloc[1]
                references.append(
                    {
                        "type": "peer",
                        "label": f"next-worst {top['dim']}: {runner_up['dim_value']}",
                        "value": round(float(runner_up["value"]) * 100, 2),
                        "unit": "percent",
                    }
                )
    return references


def _narrative(
    metric: dict[str, Any],
    overall: Totals,
    adverse: float,
    attribution: list[dict[str, Any]],
    controls: list[dict[str, Any]],
    direction: str,
    warn: float,
) -> dict[str, Any]:
    """Prose assembled from figures that also appear in structured fields.

    No LLM. The leadership pack is where generated prose belongs, and it gets
    validated against its own inputs; an insight body is read as fact and has to
    be reproducible from the numbers beside it.
    """
    rate_pct = round((overall.value or 0.0) * 100, 2)
    count = int(round(adverse))
    noun = "legs uncovered" if direction == "higher_better" else "rows affected"

    if direction == "higher_better":
        headline = f"{metric['name']} at {rate_pct}%, below the {round(warn * 100, 1)}% target"
    else:
        headline = f"{count:,} {noun}: {metric['name']} at {rate_pct}%"

    sentences = [
        f"{metric['name']} is {rate_pct}% over the window "
        f"({count:,} of {int(overall.denominator):,}), against a target of {round(warn * 100, 1)}%."
    ]
    if attribution:
        top = attribution[0]
        sentences.append(
            f"{top['value']} ({top['dim']}) carries {top['contribution_pct']}% of it "
            f"across {top['n']:,} rows."
        )
    surviving = [control for control in controls if control["survives"]]
    if surviving:
        names = " and ".join(control["control"] for control in surviving)
        sentences.append(
            f"The gap survives excluding the worst {names}, so it is not one outlier."
        )
    elif controls:
        names = " and ".join(control["control"] for control in controls)
        sentences.append(
            f"Excluding the worst {names} brings it back within target, so it is concentrated there."
        )

    action_target = attribution[0]["value"] if attribution else metric["name"]
    return {
        "headline": headline,
        "body": " ".join(sentences),
        "recommended_actions": [
            {
                "type": "ticket",
                "title": f"Investigate {metric['name'].lower()}",
                "draft": (
                    f"{metric['name']} is {rate_pct}% against a {round(warn * 100, 1)}% target, "
                    f"{count:,} {noun}. Start with {action_target}."
                ),
                "rationale": (
                    f"{attribution[0]['contribution_pct']}% attributed to {action_target}."
                    if attribution
                    else "Metric is past its declared target."
                ),
            }
        ],
    }


def _trace(
    metric: dict[str, Any],
    overall: Totals,
    attribution: list[dict[str, Any]],
    slices_by_dim: dict[str, pd.DataFrame],
    start: str,
    end: str,
    grain: str,
) -> list[dict[str, Any]]:
    exclusions = [f"rows flagged {name}" for name in metric.get("exclude_flags", [])]
    entries = [
        {
            "query_id": f"{metric['id']}__overall",
            "params": {"dim": "tenant_id", "grain": grain, "start": start, "end": end},
            "numerator": int(round(overall.numerator)),
            "denominator": int(round(overall.denominator)),
            "exclusions": exclusions,
            "validation": {
                "status": "pass",
                "notes": (
                    "numerator and denominator summed from the compiled per-period series; "
                    "recomputing the rate from them reproduces the reported value"
                ),
            },
        }
    ]
    if attribution:
        dim = attribution[0]["dim"]
        totals = slices_by_dim.get(dim)
        if totals is not None:
            entries.append(
                {
                    "query_id": f"{metric['id']}__by_{dim}",
                    "params": {"dim": dim, "grain": grain, "start": start, "end": end},
                    "numerator": int(round(float(totals["numerator"].sum()))),
                    "denominator": int(round(float(totals["denominator"].sum()))),
                    "exclusions": exclusions,
                    "validation": {
                        "status": "pass" if len(totals) > 1 else "warn",
                        "notes": (
                            f"{len(totals)} slice(s) of {dim} met min_sample; "
                            "slices below it are excluded from attribution"
                        ),
                    },
                }
            )
    return entries


def _column_is_populated(tenant_id: str, metric: dict[str, Any], start: str, end: str) -> bool:
    """Guard against reporting an unpopulated source column as an operational finding.

    A metric whose numerator keys off a column that is empty at source will read as a
    near-total breach -- "97.8% of km unbilled" -- when what it has actually measured is
    that nobody filled the field in. The registry names the column and the floor; below
    it, the metric is a data-completeness signal and detection skips it rather than
    dressing it up as a business number.
    """
    requirement = metric.get("requires_populated")
    if not requirement:
        return True
    column = requirement["column"]
    floor = float(requirement.get("min_populated_pct", 10))
    date_col = compiler.date_column(metric)
    sql = (
        f"SELECT COUNT(*) AS total, COUNT(*) FILTER (WHERE {column} IS NOT NULL "
        f"AND {column} <> 0) AS populated FROM {metric['table']} "
        f"WHERE tenant_id = ? AND {date_col} BETWEEN ? AND ?"
    )
    row = db.fetch_one(tenant_id, sql, [start, end])
    if not row or not row[0]:
        return False
    populated_pct = 100.0 * int(row[1]) / int(row[0])
    return populated_pct >= floor


def detect_metric(
    tenant_id: str,
    metric: dict[str, Any],
    start: str | None = None,
    end: str | None = None,
    grain: str = "day",
) -> dict[str, Any] | None:
    """One metric for one tenant. Returns an InsightPacket, or None if the metric
    is within target or has nothing to measure.

    With no window given, the metric is evaluated over its own table's full range.
    """
    targets = metric.get("targets") or {}
    warn, critical = targets.get("warn"), targets.get("critical")
    if warn is None or critical is None:
        return None
    if metric.get("unit") not in AGGREGATABLE_UNITS:
        return None

    if start is None or end is None:
        window = window_for(tenant_id, metric["table"], compiler.date_column(metric))
        if window is None:
            return None
        start, end = window

    if not _column_is_populated(tenant_id, metric, start, end):
        return None

    overall = _overall(tenant_id, metric["id"], start, end)
    if overall is None or overall.value is None or overall.denominator < metric["min_sample"]:
        return None

    direction = metric["direction"]
    if not _breaches(overall.value, warn, direction):
        return None

    adverse = _adverse(overall, direction)
    attribution, slices_by_dim = _attribution(tenant_id, metric, start, end, overall, direction)
    controls = _controls(
        metric, slices_by_dim, overall, direction, warn,
        skip_dim=attribution[0]["dim"] if attribution else None,
    )

    return {
        "insight_id": metric["id"],
        "metric": {
            "id": metric["id"],
            "name": metric["name"],
            "value": round(overall.value * 100, 2),
            "unit": "%",
            "n": int(overall.denominator),
            "window": f"{start}..{end}",
        },
        "entity": {"dim": "tenant", "id": tenant_id, "name": tenant_id},
        "references": _references(metric, warn, overall, attribution, slices_by_dim, direction),
        "attribution": attribution,
        "controls": controls,
        "coincident_events": [],
        "impact": _impact(tenant_id, metric, start, end, adverse),
        "data_quality": _data_quality(tenant_id, metric, start, end),
        "severity": _severity(overall.value, warn, critical, direction),
        "trace": _trace(metric, overall, attribution, slices_by_dim, start, end, grain),
        "narrative": _narrative(metric, overall, adverse, attribution, controls, direction, warn),
    }


def window_for(
    tenant_id: str, table: str = "fact_trip", date_col: str = "trip_date"
) -> tuple[str, str] | None:
    """The tenant's full data range *for one table*.

    Per table, not global, because the tables do not cover the same period: trips
    are July only, employee legs run from May, and billing is keyed on fortnightly
    cycles starting in May. Deriving one window from fact_trip and applying it to
    the others silently truncated them -- it hid 819 of orbit's 819 EV-contract
    mismatches, because their billing cycles start before July.

    Returns None when the tenant has no rows in that table at all.
    """
    row = db.fetch_one(
        tenant_id,
        f"SELECT MIN({date_col}), MAX({date_col}) FROM {table} WHERE tenant_id = ?",
    )
    if not row or row[0] is None:
        return None
    return str(row[0]), str(row[1])


def detect_tenant(
    tenant_id: str, start: str | None = None, end: str | None = None, grain: str = "day"
) -> list[dict[str, Any]]:
    """Every breaching metric for one tenant, worst first.

    An explicit window applies to every metric. Without one, each metric covers its
    own table's full range, and says which in ``metric.window``.
    """
    insights: list[dict[str, Any]] = []
    for metric in compiler.load_registry()["metrics"]:
        insight = detect_metric(tenant_id, metric, start, end, grain=grain)
        if insight is not None:
            insights.append(insight)
    insights.sort(key=lambda item: item["severity"], reverse=True)
    return insights


def tenants() -> list[str]:
    """Tenants present in the warehouse. Unscoped on purpose -- this is the query
    that discovers what the scopes are."""
    with db.connect(read_only=True) as conn:
        rows = conn.execute("SELECT DISTINCT tenant_id FROM fact_trip ORDER BY 1").fetchall()
    return [row[0] for row in rows]


# --- Scan orchestration ------------------------------------------------------
# What a scheduled run needs on top of detect_tenant: a window that does not come
# from the wall clock, and the counts scan_run records.

#: How far back a scan looks, in days, from the warehouse's own latest trip date.
DEFAULT_LOOKBACK_DAYS = 14

#: The table the scan window is anchored to. Metrics on other tables are NOT
#: clamped to it -- see `scan` for why.
ANCHOR_TABLE = "fact_trip"


def anchor_window(tenant_id: str, lookback_days: int = DEFAULT_LOOKBACK_DAYS) -> tuple[str, str] | None:
    """The scan window: the warehouse's latest trip date, and that minus
    ``lookback_days``.

    Derived from the data, never from ``date.today()``. The ride data in this
    warehouse is July 2026; a scheduled job that took the system clock would
    scan an empty window, find nothing, and write a run that looks like a
    healthy zero-signal success. The warehouse is the only thing that knows when
    "recently" was.

    None when the tenant has no trips at all.
    """
    row = db.fetch_one(
        tenant_id,
        f"SELECT MAX(trip_date) FROM {ANCHOR_TABLE} WHERE tenant_id = ?",
    )
    if not row or row[0] is None:
        return None
    end = pd.Timestamp(row[0]).date()
    start = end - pd.Timedelta(days=lookback_days)
    return str(start), str(end)


def trips_in_window(tenant_id: str, start: str, end: str) -> int:
    """Rows of fact_trip the scan looked at. The denominator behind "scanned
    N trips" in the UI status line."""
    row = db.fetch_one(
        tenant_id,
        f"SELECT COUNT(*) FROM {ANCHOR_TABLE} WHERE tenant_id = ? AND trip_date BETWEEN ? AND ?",
        [start, end],
    )
    return int(row[0]) if row and row[0] is not None else 0


def scan(tenant_id: str, lookback_days: int = DEFAULT_LOOKBACK_DAYS) -> dict[str, Any]:
    """One detection pass over the anchored window, plus the counts a scan_run
    row needs.

    The window is applied to metrics measured on ``fact_trip`` and to those only.
    The other fact tables do not cover the same period -- employee legs run from
    May, billing is keyed on fortnightly cycles that also start in May -- and
    clamping them to a fact_trip window silently truncates them. That is not
    hypothetical: measured against this warehouse, a global 14-day clamp drops
    ev_contract_mismatch_rate for both orbit and pinnacle entirely, because
    their billing cycles begin before the window does. Same trap ``window_for``
    documents, one level up.

    So ``window_start``/``window_end`` in the result are the scan's anchor -- the
    trip window it is reporting on, and the thing that must never come from the
    system clock -- while a metric on another table still states its own range in
    ``metric.window``.
    """
    window = anchor_window(tenant_id, lookback_days)
    if window is None:
        return {
            "tenant_id": tenant_id,
            "window_start": None,
            "window_end": None,
            "trips_scanned": 0,
            "signals_detected": 0,
            "insights": [],
        }

    start, end = window
    anchored_ids = {
        metric["id"] for metric in compiler.load_registry()["metrics"]
        if metric.get("table") == ANCHOR_TABLE
    }

    insights: list[dict[str, Any]] = []
    for metric in compiler.load_registry()["metrics"]:
        if metric["id"] in anchored_ids:
            insight = detect_metric(tenant_id, metric, start, end)
        else:
            insight = detect_metric(tenant_id, metric)
        if insight is not None:
            insights.append(insight)
    insights.sort(key=lambda item: item["severity"], reverse=True)

    return {
        "tenant_id": tenant_id,
        "window_start": start,
        "window_end": end,
        "trips_scanned": trips_in_window(tenant_id, start, end),
        # Metrics that breached their target. What survives persistence and
        # persona assembly is counted by the caller as signals_surfaced.
        "signals_detected": len(insights),
        "insights": insights,
    }
