"""Compile registry.yaml metric definitions into parameterised SQL.

Every metric compiles to exactly this shape:

    SELECT {dim} AS dim_value,
           date_trunc('{grain}', trip_date) AS period,
           {numerator}::double / NULLIF({denominator},0) AS value,
           {denominator} AS n
    FROM {table}
    WHERE tenant_id = ? AND trip_date BETWEEN ? AND ?
      AND (dq_flags & {excluded_mask}) = 0
    GROUP BY 1,2

``metric_id`` and ``dim`` are the only caller-supplied strings that reach
the SQL text, and both are validated against registry.yaml before use:
a metric_id must be a declared metric, and dim must be one of that
metric's declared slice_by columns. Nothing not already declared in the
registry can reach the query -- both are rejected with ValueError.

Grain: ride_data covers July only (four weeks), so weekly grain gives
just four baseline points, which is not enough for EWMA. 'day' is the
default; 'week' is also supported.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from app import db
from app.ingest import quality

REGISTRY_PATH = Path(__file__).with_name("registry.yaml")

#: Fact tables do not agree on what to call their date. fact_trip and
#: fact_trip_employee have trip_date; fact_trip_billing is keyed on a billing
#: cycle and has cycle_start. A metric declares its own via date_column.
DEFAULT_DATE_COLUMN = "trip_date"

_SQL_TEMPLATE = """\
SELECT {dim} AS dim_value,
       date_trunc('{grain}', {date_column}) AS period,
       {numerator}::double / NULLIF({denominator},0) AS value,
       {denominator} AS n
FROM {table}
WHERE tenant_id = ? AND {date_column} BETWEEN ? AND ?
  AND (dq_flags & {excluded_mask}) = 0
GROUP BY 1,2
"""


@lru_cache(maxsize=1)
def load_registry() -> dict[str, Any]:
    with open(REGISTRY_PATH) as f:
        return yaml.safe_load(f)


def _metrics_by_id() -> dict[str, dict[str, Any]]:
    return {m["id"]: m for m in load_registry()["metrics"]}


def get_metric(metric_id: str) -> dict[str, Any]:
    metrics = _metrics_by_id()
    if metric_id not in metrics:
        raise ValueError(f"unknown metric {metric_id!r}; declared metrics are {sorted(metrics)}")
    return metrics[metric_id]


def _validate_dim(metric: dict[str, Any], dim: str) -> str:
    allowed = metric["slice_by"]
    if dim not in allowed:
        raise ValueError(
            f"dimension {dim!r} is not declared for metric {metric['id']!r}; allowed: {allowed}"
        )
    return dim


def _validate_grain(grain: str) -> str:
    allowed = load_registry().get("supported_grains", ["day", "week"])
    if grain not in allowed:
        raise ValueError(f"unsupported grain {grain!r}; supported grains: {allowed}")
    return grain


def compile_sql(metric_id: str, dim: str, grain: str = "day") -> str:
    """Compile one metric, sliced by one dimension, to parameterised SQL.

    Returned SQL has three ``?`` placeholders, in order: tenant_id,
    period start (inclusive), period end (inclusive) -- matching what
    app/db.py's fetch_df binds tenant_id against.
    """
    metric = get_metric(metric_id)
    dim = _validate_dim(metric, dim)
    grain = _validate_grain(grain)
    excluded_mask = quality.mask_from_names(metric.get("exclude_flags", []))

    return _SQL_TEMPLATE.format(
        dim=dim,
        grain=grain,
        numerator=metric["numerator"],
        denominator=metric["denominator"],
        table=metric["table"],
        date_column=date_column(metric),
        excluded_mask=excluded_mask,
    )


def date_column(metric: dict[str, Any]) -> str:
    """The date column a metric filters and groups on."""
    return metric.get("date_column", DEFAULT_DATE_COLUMN)


def run_metric(
    tenant_id: str,
    metric_id: str,
    dim: str,
    start_date: str,
    end_date: str,
    grain: str = "day",
) -> pd.DataFrame:
    """Compile and execute one metric against the warehouse.

    Rows whose sample size ``n`` falls below the metric's declared
    min_sample keep ``n`` visible but have ``value`` nulled out, so
    thin slices don't masquerade as confident readings.
    """
    metric = get_metric(metric_id)
    sql = compile_sql(metric_id, dim, grain)
    result = db.fetch_df(tenant_id, sql, [start_date, end_date])
    below_min_sample = result["n"] < metric["min_sample"]
    result.loc[below_min_sample, "value"] = None
    return result
