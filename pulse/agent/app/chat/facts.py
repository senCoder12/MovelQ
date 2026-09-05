"""Chat-time enrichment of one InsightPacket.

The eight intents ask things the packet almost, but not quite, already
answers. The packet carries the top three attribution slices; "why this
dimension and not the vendor" needs the full ranked list. It carries a
leave-one-out control; "couldn't this just be the vendor" is better answered
by whether the gap holds *within* every vendor. It carries an excluded-row
percentage; "what if those rows change this" needs the bound they put on the
number.

So this module computes those extras -- deterministically, from the same
registry-declared metric the packet came from, with no query the compiler
could not have produced itself. Nothing here is a new measurement: every
figure is the same numerator and denominator the detector used, sliced or
bounded differently.

Three rules hold throughout:

  * No free-form SQL. Dimensions are validated against the metric's declared
    ``slice_by`` before they reach a query, exactly as app/metrics/compiler.py
    does, and the one row-level query (examples) is a fixed template per
    metric with the limit bound as a parameter.
  * No model. This module is on the same side of the line as app/detect.
  * Nothing invented. Where a figure is not derivable -- a start date that
    cannot be inferred, exclusion bounds for a metric whose denominator is
    itself filtered -- the field says so rather than carrying a guess.

The result is attached to the packet as ``chat_facts``; app/chat/templates.py
reads it, and eval/run_eval.py treats packet + chat_facts as the one source
every number in an answer must trace back to.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from app import db
from app.detect import signals
from app.ingest import quality
from app.metrics import compiler

#: Minimum days either side of a split before a step in the daily series is
#: allowed to be called a change point. Below this a single noisy day at one
#: end of the window would read as a regime change.
MIN_CHANGE_POINT_SIDE_DAYS = 5

#: A step in the daily rate must clear both of these to be reported: this many
#: robust SDs of the daily series, and this many percentage points outright.
CHANGE_POINT_SIGMA = 3.0
CHANGE_POINT_MIN_STEP_PP = 5.0

#: MAD -> sigma for a normal distribution. Used only to give "how far past
#: target" a scale that a couple of loud days cannot inflate.
MAD_TO_SIGMA = 1.4826

#: User-facing control aliases (app/chat/intents.py) mapped onto the slice
#: columns metrics actually declare. A metric that declares none of a name's
#: columns has not tested that control, and the template says exactly that.
CONTROL_ALIASES: dict[str, tuple[str, ...]] = {
    "vendor": ("vendor_id", "vendor"),
    "hour": ("shift_bucket", "shift_suffix"),
    "office": ("office", "site_code"),
}

#: How a dimension is described in prose. Anything not listed is rendered as
#: its column name in mono, which is honest if ugly.
DIM_LABELS: dict[str, str] = {
    "vendor_id": "vendor",
    "vendor": "vendor",
    "office": "office",
    "site_code": "site",
    "shift_bucket": "time-of-day bucket",
    "shift_suffix": "shift-code suffix",
    "route_source": "route source",
    "product_type": "product type",
    "contract": "contract",
    "emp_role": "employee role",
}


def dim_label(dim: str) -> str:
    return DIM_LABELS.get(dim, dim)


@dataclass(frozen=True)
class ExampleQuery:
    """One whitelisted row-level query: which table, which rows count as the
    adverse ones, and which columns are safe to show.

    The predicate restates the metric's numerator FILTER at row level -- the
    registry's version is an aggregate expression and cannot be reused as a
    WHERE clause. tests/test_chat_facts.py asserts the two agree by counting:
    rows matching this predicate must equal the packet's numerator.
    """

    table: str
    date_column: str
    predicate: str
    select: str
    columns: tuple[tuple[str, str], ...]


#: The only row-level queries chat can run. Keyed by metric id: a metric with
#: no entry here answers SHOW_ME_EXAMPLES with "not available", never with an
#: improvised query.
EXAMPLE_QUERIES: dict[str, ExampleQuery] = {
    "delay_reconciliation_gap": ExampleQuery(
        table="fact_trip",
        date_column="trip_date",
        predicate="computed_arrival_delay_min > 10 AND reported_delay_minutes = 0",
        select=(
            "trip_id, trip_date, vendor_id, shift_type, "
            "strftime(to_timestamp(planned_end_epoch), '%Y-%m-%d %H:%M') AS planned_end, "
            "strftime(to_timestamp(actual_end_epoch), '%Y-%m-%d %H:%M') AS actual_end, "
            "round(computed_arrival_delay_min, 1) AS computed_delay_min, "
            "reported_delay_minutes AS reported_delay_min"
        ),
        columns=(
            ("trip_id", "Trip"),
            ("trip_date", "Date"),
            ("vendor_id", "Vendor"),
            ("shift_type", "Shift"),
            ("planned_end", "Planned end"),
            ("actual_end", "Actual end"),
            ("computed_delay_min", "Computed delay (min)"),
            ("reported_delay_min", "Reported delay (min)"),
        ),
    ),
    "ota": ExampleQuery(
        table="fact_trip",
        date_column="trip_date",
        predicate="computed_arrival_delay_min > 0",
        select=(
            "trip_id, trip_date, vendor_id, shift_type, "
            "strftime(to_timestamp(planned_end_epoch), '%Y-%m-%d %H:%M') AS planned_end, "
            "strftime(to_timestamp(actual_end_epoch), '%Y-%m-%d %H:%M') AS actual_end, "
            "round(computed_arrival_delay_min, 1) AS computed_delay_min, "
            "reported_delay_minutes AS reported_delay_min"
        ),
        columns=(
            ("trip_id", "Trip"),
            ("trip_date", "Date"),
            ("vendor_id", "Vendor"),
            ("shift_type", "Shift"),
            ("planned_end", "Planned end"),
            ("actual_end", "Actual end"),
            ("computed_delay_min", "Computed delay (min)"),
            ("reported_delay_min", "Reported delay (min)"),
        ),
    ),
    "on_time_departure": ExampleQuery(
        table="fact_trip",
        date_column="trip_date",
        predicate="computed_start_delay_min > 0",
        select=(
            "trip_id, trip_date, vendor_id, shift_type, "
            "strftime(to_timestamp(planned_start_epoch), '%Y-%m-%d %H:%M') AS planned_start, "
            "strftime(to_timestamp(actual_start_epoch), '%Y-%m-%d %H:%M') AS actual_start, "
            "round(computed_start_delay_min, 1) AS computed_delay_min, "
            "reported_delay_minutes AS reported_delay_min"
        ),
        columns=(
            ("trip_id", "Trip"),
            ("trip_date", "Date"),
            ("vendor_id", "Vendor"),
            ("shift_type", "Shift"),
            ("planned_start", "Planned start"),
            ("actual_start", "Actual start"),
            ("computed_delay_min", "Computed delay (min)"),
            ("reported_delay_min", "Reported delay (min)"),
        ),
    ),
}


# --- small helpers ------------------------------------------------------------

def _pct(value: float | None) -> float | None:
    return None if value is None else round(value * 100, 2)


def _window(insight: dict[str, Any]) -> tuple[str, str]:
    window = str(insight.get("metric", {}).get("window", ""))
    start, _, end = window.partition("..")
    if not start or not end:
        raise ValueError(f"insight metric.window is not 'start..end': {window!r}")
    return start, end


def tenant_of(insight: dict[str, Any]) -> str | None:
    """The tenant an insight belongs to, when it is tenant-scoped. Chat needs
    one to re-slice the metric; a packet without it can only be answered from
    fields it already carries."""
    entity = insight.get("entity") or {}
    return entity.get("id") if entity.get("dim") == "tenant" else None


def _robust_sigma_pp(daily: pd.Series) -> float:
    """Robust SD of a daily rate series, in percentage points. 0 when the
    series is too short or perfectly flat -- callers guard on that rather than
    dividing by it."""
    if daily.empty:
        return 0.0
    median = float(daily.median())
    mad = float((daily - median).abs().median())
    return round(MAD_TO_SIGMA * mad * 100, 4)


# --- the pieces ---------------------------------------------------------------

def _attribution_ranked(
    slices: dict[str, pd.DataFrame],
    overall: signals.Totals,
    direction: str,
    warn: float,
) -> list[dict[str, Any]]:
    """Every slice value on every declared dimension, ranked by its share of
    the adverse rows.

    The packet keeps the top three. This is the same computation with no cut
    and no minimum contribution, because "why this dimension and not the
    vendor" is a question about the entries that did *not* make the list.
    """
    total_adverse = signals._adverse(overall, direction)
    ranked: list[dict[str, Any]] = []
    for dim, totals in slices.items():
        for row in totals.itertuples():
            entity = signals.Totals(float(row.numerator), float(row.denominator))
            adverse = signals._adverse(entity, direction)
            value = entity.value
            gap = (warn - value) if direction == "higher_better" else (value - warn)
            ranked.append(
                {
                    "dim": dim,
                    "dim_label": dim_label(dim),
                    "value": str(row.dim_value),
                    "contribution_pct": round(100.0 * adverse / total_adverse, 1) if total_adverse else 0.0,
                    "n": int(row.denominator),
                    "rate_pct": _pct(value),
                    "gap_pp": round(gap * 100, 1),
                    "adverse": int(round(adverse)),
                }
            )
    ranked.sort(key=lambda item: item["contribution_pct"], reverse=True)

    # Ranks are carried, not derived at render time: an answer that says
    # "3rd of 21" has to be able to point at both numbers in a field.
    per_dim: dict[str, int] = {}
    dim_counts = {dim: len(totals) for dim, totals in slices.items()}
    for position, entry in enumerate(ranked, start=1):
        per_dim[entry["dim"]] = per_dim.get(entry["dim"], 0) + 1
        entry["rank"] = position
        entry["rank_in_dim"] = per_dim[entry["dim"]]
        entry["slices_in_dim"] = dim_counts[entry["dim"]]
        entry["slices_ranked"] = len(ranked)
    return ranked


def _controls_detail(
    slices: dict[str, pd.DataFrame],
    overall: signals.Totals,
    direction: str,
    warn: float,
    min_sample: int,
) -> list[dict[str, Any]]:
    """Two controls per dimension, because they answer different objections.

    ``within``: hold the dimension fixed and check the gap inside every one of
    its values. If the effect were a mix artefact -- one bad vendor dragging a
    fleet average -- controlling for vendor would collapse it. This is what a
    challenge like "couldn't this just be the vendor" actually asks.

    ``leave_one_out``: drop the single worst value and recompute, which is what
    the packet's ``controls[]`` already carries. Kept alongside so the answer
    can cite the figure the insight card shows.
    """
    detail: list[dict[str, Any]] = []
    for dim, totals in slices.items():
        eligible = totals[totals["denominator"] >= min_sample]
        if eligible.empty:
            continue

        gaps = []
        holding = 0
        for row in eligible.itertuples():
            value = float(row.numerator) / float(row.denominator)
            gap = (warn - value) if direction == "higher_better" else (value - warn)
            gaps.append(gap * 100)
            if signals._breaches(value, warn, direction):
                holding += 1

        adverse = totals.apply(
            lambda row: signals._adverse(
                signals.Totals(float(row["numerator"]), float(row["denominator"])), direction
            ),
            axis=1,
        )
        worst = totals.loc[adverse.idxmax()]
        remaining = signals.Totals(
            overall.numerator - float(worst["numerator"]),
            overall.denominator - float(worst["denominator"]),
        )
        loo_gap_pp = None
        loo_survives = None
        if remaining.denominator > 0 and remaining.value is not None:
            loo = (warn - remaining.value) if direction == "higher_better" else (remaining.value - warn)
            loo_gap_pp = round(loo * 100, 1)
            loo_survives = bool(signals._breaches(remaining.value, warn, direction))

        detail.append(
            {
                "control": dim,
                "dim_label": dim_label(dim),
                "tested": True,
                "n_entities": len(gaps),
                "n_holding": holding,
                "all_hold": holding == len(gaps),
                "mean_gap_pp": round(sum(gaps) / len(gaps), 1),
                "min_gap_pp": round(min(gaps), 1),
                "max_gap_pp": round(max(gaps), 1),
                "worst_entity": str(worst["dim_value"]),
                "leave_one_out_gap_pp": loo_gap_pp,
                "leave_one_out_survives": loo_survives,
            }
        )
    detail.sort(key=lambda item: item["n_entities"], reverse=True)
    return detail


def _sample(
    overall: signals.Totals,
    daily: pd.Series,
    metric: dict[str, Any],
    warn: float,
    direction: str,
) -> dict[str, Any]:
    """Sample size against the metric's declared floor, and how far past target
    the window sits measured in day-to-day variation.

    Not a significance test and not labelled as one: the spread is the metric's
    own daily series, so the figure says "this is far outside the range this
    metric moves in", which is the claim the answer makes."""
    value = overall.value or 0.0
    sigma_pp = _robust_sigma_pp(daily)
    gap_pp = ((warn - value) if direction == "higher_better" else (value - warn)) * 100
    return {
        "n": int(overall.denominator),
        "min_sample": int(metric["min_sample"]),
        "meets_min_sample": overall.denominator >= metric["min_sample"],
        "times_min_sample": round(overall.denominator / metric["min_sample"], 1) if metric["min_sample"] else None,
        "target_pct": round(warn * 100, 2),
        "value_pct": _pct(value),
        "gap_pp": round(gap_pp, 2),
        "daily_points": int(daily.shape[0]),
        "daily_median_pct": _pct(float(daily.median())) if not daily.empty else None,
        "daily_min_pct": _pct(float(daily.min())) if not daily.empty else None,
        "daily_max_pct": _pct(float(daily.max())) if not daily.empty else None,
        "robust_sigma_pp": sigma_pp,
        # None, not 0, when the daily series never moves: "infinitely many SDs
        # past target" is not a number worth printing.
        "robust_z": round(gap_pp / sigma_pp, 1) if sigma_pp > 0 else None,
    }


def _exclusions(
    tenant_id: str,
    metric: dict[str, Any],
    start: str,
    end: str,
    overall: signals.Totals,
    direction: str,
    warn: float,
    data_quality: dict[str, Any],
) -> dict[str, Any]:
    """What the excluded rows could do to the number if every one of them went
    the wrong way.

    Bounds are only derivable when the metric's denominator counts every row:
    for a metric whose denominator is itself filtered (EV contracts, night
    female legs) adding excluded rows to it would be arithmetic about a
    population the metric never measured. Those get ``bounds_derivable: false``
    and the answer says why.
    """
    excluded_mask = quality.mask_from_names(metric.get("exclude_flags", []))
    date_col = compiler.date_column(metric)
    sql = (
        "SELECT COUNT(*) AS total, "
        f"COUNT(*) FILTER (WHERE (dq_flags & {excluded_mask}) <> 0) AS excluded "
        f"FROM {metric['table']} WHERE tenant_id = ? AND {date_col} BETWEEN ? AND ?"
    )
    row = db.fetch_one(tenant_id, sql, [start, end])
    total_rows, excluded_rows = (int(row[0]), int(row[1])) if row else (0, 0)

    facts: dict[str, Any] = {
        "excluded_pct": data_quality.get("excluded_pct"),
        "confidence": data_quality.get("confidence"),
        "excluded_rows": excluded_rows,
        "total_rows": total_rows,
        "excluded_flags": list(metric.get("exclude_flags", [])),
        "reported_pct": _pct(overall.value),
        "bounds_derivable": False,
        "bounds_note": (
            "the denominator counts only a subset of rows, so the excluded rows "
            "cannot be added back to it"
        ),
    }

    if metric["denominator"].strip().upper() != "COUNT(*)" or excluded_rows == 0:
        return facts

    widened = overall.denominator + excluded_rows
    if direction == "higher_better":
        best = (overall.numerator + excluded_rows) / widened
        worst = overall.numerator / widened
    else:
        best = overall.numerator / widened
        worst = (overall.numerator + excluded_rows) / widened

    facts.update(
        {
            "bounds_derivable": True,
            "bounds_note": (
                "every excluded row assumed to fall the same way, which is the "
                "widest the number can move"
            ),
            "best_case_pct": _pct(best),
            "worst_case_pct": _pct(worst),
            "best_case_breaches": bool(signals._breaches(best, warn, direction)),
            "worst_case_breaches": bool(signals._breaches(worst, warn, direction)),
        }
    )
    return facts


def _timeline(
    frame: pd.DataFrame, warn: float, direction: str, start: str, end: str, insight: dict[str, Any]
) -> dict[str, Any]:
    """When it started, or why that is not answerable.

    A change point is only reported when a split of the daily series produces a
    step that clears both a robust-SD threshold and a floor in percentage
    points, with enough days either side to be a regime rather than a spike.
    Otherwise the answer is that no start date is inferable, and the fields
    below are what makes that a statement rather than a shrug: how much of the
    window is covered, how steady the volume is, and how many days sit past
    target.
    """
    ordered = frame.dropna(subset=["value"]).sort_values("period")
    values = ordered["value"].astype(float).reset_index(drop=True)
    counts = ordered["n"].astype(float).reset_index(drop=True)
    days = int(values.shape[0])

    volume_mean = float(counts.mean()) if days else 0.0
    volume_cv_pct = round(100.0 * float(counts.std(ddof=0)) / volume_mean, 1) if volume_mean else None
    breaching = [bool(signals._breaches(float(v), warn, direction)) for v in values]

    timeline: dict[str, Any] = {
        "window_start": start,
        "window_end": end,
        "first_day": str(ordered["period"].iloc[0])[:10] if days else None,
        "last_day": str(ordered["period"].iloc[-1])[:10] if days else None,
        "days_with_data": days,
        "days_past_target": sum(breaching),
        "days_within_target": days - sum(breaching),
        "volume_mean_per_day": int(round(volume_mean)) if days else 0,
        "volume_cv_pct": volume_cv_pct,
        "coincident_events": list(insight.get("coincident_events") or []),
        "change_point": None,
        "change_point_step_pp": None,
        "change_point_reason": "",
    }

    sigma_pp = _robust_sigma_pp(values)
    threshold_pp = max(CHANGE_POINT_SIGMA * sigma_pp, CHANGE_POINT_MIN_STEP_PP)
    timeline["change_point_threshold_pp"] = round(threshold_pp, 1)

    if days < 2 * MIN_CHANGE_POINT_SIDE_DAYS:
        timeline["change_point_reason"] = (
            f"the series has {days} day(s) with data, fewer than the "
            f"{2 * MIN_CHANGE_POINT_SIDE_DAYS} a before/after split needs"
        )
        return timeline

    best_split, best_step = None, 0.0
    for split in range(MIN_CHANGE_POINT_SIDE_DAYS, days - MIN_CHANGE_POINT_SIDE_DAYS + 1):
        step = (float(values[split:].mean()) - float(values[:split].mean())) * 100
        if abs(step) > abs(best_step):
            best_split, best_step = split, step

    timeline["largest_step_pp"] = round(best_step, 1)
    if best_split is not None and abs(best_step) >= threshold_pp:
        timeline["change_point"] = str(ordered["period"].iloc[best_split])[:10]
        timeline["change_point_step_pp"] = round(best_step, 1)
        timeline["change_point_reason"] = (
            f"the daily rate steps by {round(best_step, 1)}pp at that date, past the "
            f"{round(threshold_pp, 1)}pp threshold for this series"
        )
    else:
        timeline["change_point_reason"] = (
            f"the largest before/after step anywhere in the window is "
            f"{round(best_step, 1)}pp, under the {round(threshold_pp, 1)}pp a start "
            "date would need"
        )
    return timeline


def _examples_meta(
    metric: dict[str, Any], insight: dict[str, Any], start: str, end: str
) -> dict[str, Any]:
    """What SHOW_ME_EXAMPLES would run, without running it.

    The filter is the packet's own: the metric's window and exclusions, the
    adverse predicate, and -- when the top attribution slice is a column of the
    same table -- that slice, so "show me some of these trips" shows trips from
    the cohort the finding is about rather than a random adverse sample.
    """
    query = EXAMPLE_QUERIES.get(metric["id"])
    if query is None:
        return {
            "available": False,
            "reason": f"no row-level view is whitelisted for {metric['id']}",
        }

    attribution = (insight.get("attribution") or [])
    slice_dim = slice_value = None
    for entry in attribution:
        if entry.get("dim") in metric["slice_by"] and entry.get("dim") != "tenant_id":
            slice_dim, slice_value = entry["dim"], entry["value"]
            break

    return {
        "available": True,
        "query_id": f"{metric['id']}__examples",
        "table": query.table,
        "predicate": query.predicate,
        "window": f"{start}..{end}",
        "exclusions": [f"rows flagged {name}" for name in metric.get("exclude_flags", [])],
        "slice_dim": slice_dim,
        "slice_dim_label": dim_label(slice_dim) if slice_dim else None,
        "slice_value": slice_value,
        "columns": [{"key": key, "label": label} for key, label in query.columns],
    }


def fetch_examples(
    tenant_id: str, insight: dict[str, Any], limit: int
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Run the one whitelisted row-level query for this insight.

    ``limit`` is bound as a parameter, never interpolated, and is already
    clamped to 1..25 by app/chat/intents.py. The dimension used for the slice
    filter is validated against the metric's declared ``slice_by`` before it
    reaches the SQL text -- the same rule app/metrics/compiler.py applies.
    """
    metric = compiler.get_metric(insight["metric"]["id"])
    start, end = _window(insight)
    meta = _examples_meta(metric, insight, start, end)
    if not meta["available"]:
        return [], meta

    query = EXAMPLE_QUERIES[metric["id"]]
    excluded_mask = quality.mask_from_names(metric.get("exclude_flags", []))
    where = [
        "tenant_id = ?",
        f"{query.date_column} BETWEEN ? AND ?",
        f"(dq_flags & {excluded_mask}) = 0",
        query.predicate,
    ]
    params: list[Any] = [start, end]

    slice_dim = meta.get("slice_dim")
    if slice_dim:
        if slice_dim not in metric["slice_by"]:
            raise ValueError(f"dimension {slice_dim!r} is not declared for {metric['id']!r}")
        where.append(f"{slice_dim} = ?")
        params.append(meta["slice_value"])

    sql = (
        f"SELECT {query.select} FROM {query.table} "
        f"WHERE {' AND '.join(where)} "
        f"ORDER BY {query.date_column}, trip_id LIMIT ?"
    )
    frame = db.fetch_df(tenant_id, sql, [*params, int(limit)])
    rows = [
        {key: (None if pd.isna(value) else value) for key, value in record.items()}
        for record in frame.astype(object).to_dict(orient="records")
    ]
    for row in rows:
        for key, value in row.items():
            if isinstance(value, float) and value.is_integer():
                row[key] = int(value)
            elif hasattr(value, "isoformat"):
                row[key] = value.isoformat()[:10]
    return rows, meta


def build(insight: dict[str, Any], action_drafts: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """The insight with ``chat_facts`` attached.

    Returns a copy: the caller's packet is the one Java persisted and rendered,
    and chat does not mutate it. When the extras cannot be computed -- a packet
    with no tenant scope, a metric no longer in the registry, a warehouse that
    is not there -- ``chat_facts`` carries ``available: false`` and the
    templates fall back to what the packet itself holds.
    """
    enriched = dict(insight)
    enriched["chat_facts"] = _build_facts(insight, action_drafts or [])
    return enriched


def _build_facts(insight: dict[str, Any], action_drafts: list[dict[str, Any]]) -> dict[str, Any]:
    base: dict[str, Any] = {
        "available": False,
        "reason": "",
        "action_drafts": [
            {
                "type": draft.get("type"),
                "title": draft.get("title"),
                "status": draft.get("status"),
            }
            for draft in action_drafts
        ],
    }

    tenant_id = tenant_of(insight)
    if not tenant_id:
        base["reason"] = "this insight is not tenant-scoped, so its slices cannot be recomputed"
        return base

    try:
        metric = compiler.get_metric(insight["metric"]["id"])
        start, end = _window(insight)
    except (KeyError, ValueError) as exc:
        base["reason"] = str(exc)
        return base

    targets = metric.get("targets") or {}
    warn = targets.get("warn")
    direction = metric["direction"]
    if warn is None:
        base["reason"] = f"{metric['id']} declares no warn target to measure a gap against"
        return base

    try:
        overall = signals._overall(tenant_id, metric["id"], start, end)
        if overall is None or overall.value is None:
            base["reason"] = "the metric produced no series for this window"
            return base
        slices = {
            dim: totals
            for dim in metric["slice_by"]
            if dim != "tenant_id"
            for totals in [signals._totals_by_dim(tenant_id, metric["id"], dim, start, end)]
            if not totals.empty
        }
        frame = compiler.run_metric(tenant_id, metric["id"], "tenant_id", start, end, grain="day")
    except Exception as exc:  # warehouse missing, file locked, schema drift
        base["reason"] = f"the warehouse could not be re-read for this insight: {exc}"
        return base

    daily = frame.dropna(subset=["value"])["value"].astype(float)

    base.update(
        {
            "available": True,
            "metric_id": metric["id"],
            "metric_name": metric["name"],
            "direction": direction,
            "window": f"{start}..{end}",
            "attribution_ranked": _attribution_ranked(slices, overall, direction, warn),
            "attribution_dims": [dim_label(dim) for dim in slices],
            "controls_detail": _controls_detail(
                slices, overall, direction, warn, int(metric["min_sample"])
            ),
            "sample": _sample(overall, daily, metric, warn, direction),
            "exclusions": _exclusions(
                tenant_id, metric, start, end, overall, direction, warn,
                insight.get("data_quality") or {},
            ),
            "timeline": _timeline(frame, warn, direction, start, end, insight),
            "examples": _examples_meta(metric, insight, start, end),
        }
    )
    return base


def control_for(facts: dict[str, Any], control_name: str) -> dict[str, Any] | None:
    """The controls_detail entry a user-facing control name maps onto, or None
    when that control was not tested for this metric."""
    detail = facts.get("controls_detail") or []
    for column in CONTROL_ALIASES.get(control_name, ()):
        for entry in detail:
            if entry["control"] == column:
                return entry
    return None


def tested_control_labels(facts: dict[str, Any]) -> list[str]:
    return [entry["dim_label"] for entry in facts.get("controls_detail") or []]
