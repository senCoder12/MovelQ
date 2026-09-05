"""What the model calls cost -- the query behind GET /api/metrics/cost.

Reads token_usage for one tenant and period and returns a breakdown that can be
pasted into a slide without further arithmetic: calls by type with token sums
and mean duration, the cache hit rate, total tokens, an estimated cost from the
rate table in app/llm/rates.yaml, and the three derived figures anyone asks for
next -- cost per scan, cost per insight, cost per tenant-day.

Two things this deliberately does not do:

* It does not price a model that is not in the rate table. Those calls are
  counted, their tokens are summed, and the model is named under
  ``unpriced_models`` -- an estimate that quietly treated an unknown model as
  free would understate the bill in exactly the situation where someone has
  just switched models.
* It does not alert, budget or enforce. It reports.

Cost per scan divides by the number of *distinct scan runs represented in the
ledger for the period*, not by the number of scan_run rows: a scan that made no
model calls has no rows here, and including it would flatter the average by
dividing the same spend across more runs.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml

from app import platform_db

log = logging.getLogger(__name__)

RATES_PATH = Path(__file__).with_name("rates.yaml")

#: Default reporting period when the caller names none.
DEFAULT_PERIOD_DAYS = 30

_TOKENS_PER_UNIT = 1_000_000


def load_rates() -> tuple[dict[str, dict[str, float]], str]:
    """(rates by model, currency) from app/llm/rates.yaml.

    A missing or malformed file is not fatal: the breakdown is still useful
    without a price on it, and failing the whole endpoint over a config file
    would take the token counts down with the estimate.
    """
    try:
        with open(RATES_PATH) as handle:
            document = yaml.safe_load(handle) or {}
    except (OSError, yaml.YAMLError) as exc:
        log.warning("could not read %s: %s", RATES_PATH, exc)
        return {}, "USD"
    section = ((document.get("pulse") or {}).get("llm") or {})
    return section.get("rates") or {}, section.get("currency") or "USD"


_SUMMARY_SQL = """
SELECT call_type,
       COUNT(*)                                              AS calls,
       COALESCE(SUM(tokens_in), 0)                           AS tokens_in,
       COALESCE(SUM(tokens_out), 0)                          AS tokens_out,
       COALESCE(SUM(cached_tokens), 0)                       AS cached_tokens,
       COALESCE(AVG(duration_ms), 0)                         AS mean_duration_ms,
       COUNT(*) FILTER (WHERE cache_hit)                     AS cache_hits,
       COUNT(*) FILTER (WHERE error IS NOT NULL)             AS errors
  FROM token_usage
 WHERE tenant_id = %s AND created_at >= %s AND created_at < %s
 GROUP BY call_type
 ORDER BY calls DESC
"""

_BY_MODEL_SQL = """
SELECT model,
       COUNT(*)                        AS calls,
       COALESCE(SUM(tokens_in), 0)     AS tokens_in,
       COALESCE(SUM(tokens_out), 0)    AS tokens_out,
       COALESCE(SUM(cached_tokens), 0) AS cached_tokens
  FROM token_usage
 WHERE tenant_id = %s AND created_at >= %s AND created_at < %s
 GROUP BY model
 ORDER BY calls DESC
"""

_DENOMINATORS_SQL = """
SELECT COUNT(DISTINCT scan_run_id) FILTER (WHERE scan_run_id IS NOT NULL) AS scans,
       COUNT(DISTINCT insight_id)  FILTER (WHERE insight_id  IS NOT NULL) AS insights
  FROM token_usage
 WHERE tenant_id = %s AND created_at >= %s AND created_at < %s
"""


def _window(start: str | None, end: str | None) -> tuple[datetime, datetime]:
    """[start, end) as timezone-aware UTC. ``end`` is exclusive and defaults to
    the start of tomorrow, so "today" is included in a default period."""
    end_date = date.fromisoformat(end) + timedelta(days=1) if end else \
        datetime.now(timezone.utc).date() + timedelta(days=1)
    start_date = date.fromisoformat(start) if start else end_date - timedelta(days=DEFAULT_PERIOD_DAYS)
    to_utc = lambda value: datetime(value.year, value.month, value.day, tzinfo=timezone.utc)  # noqa: E731
    return to_utc(start_date), to_utc(end_date)


def _estimate(tokens_in: int, tokens_out: int, rate: dict[str, float] | None) -> float | None:
    if not rate:
        return None
    return (
        tokens_in * float(rate.get("input", 0.0)) / _TOKENS_PER_UNIT
        + tokens_out * float(rate.get("output", 0.0)) / _TOKENS_PER_UNIT
    )


def _round_money(value: float) -> float:
    """Six decimals. A single Flash call costs fractions of a cent, and rounding
    to two would report most of this table as 0.00."""
    return round(value, 6)


def cost_report(tenant_id: str, start: str | None = None, end: str | None = None) -> dict[str, Any]:
    """The breakdown for one tenant over ``[start, end]`` (inclusive dates).

    Raises RuntimeError when the platform database is unreachable -- unlike a
    ledger write, this is a query someone asked for, and returning zeros would
    be indistinguishable from a period in which nothing ran.
    """
    if not tenant_id or not tenant_id.strip():
        raise ValueError("tenant_id is required")

    window_start, window_end = _window(start, end)
    params = (tenant_id, window_start, window_end)

    by_call_type = platform_db.fetch_all(_SUMMARY_SQL, params)
    by_model = platform_db.fetch_all(_BY_MODEL_SQL, params)
    scans, insights = platform_db.fetch_all(_DENOMINATORS_SQL, params)[0]

    rates, currency = load_rates()

    calls_rows: list[dict[str, Any]] = []
    total_calls = total_in = total_out = total_cached = total_hits = total_errors = 0
    for call_type, calls, tokens_in, tokens_out, cached, mean_ms, hits, errors in by_call_type:
        calls_rows.append({
            "call_type": call_type,
            "calls": int(calls),
            "tokens_in": int(tokens_in),
            "tokens_out": int(tokens_out),
            "cached_tokens": int(cached),
            "mean_duration_ms": round(float(mean_ms), 1),
            "cache_hits": int(hits),
            "errors": int(errors),
        })
        total_calls += int(calls)
        total_in += int(tokens_in)
        total_out += int(tokens_out)
        total_cached += int(cached)
        total_hits += int(hits)
        total_errors += int(errors)

    model_rows: list[dict[str, Any]] = []
    unpriced: list[str] = []
    estimated_total = 0.0
    for model, calls, tokens_in, tokens_out, cached in by_model:
        estimate = _estimate(int(tokens_in), int(tokens_out), rates.get(model))
        if estimate is None:
            unpriced.append(model)
        else:
            estimated_total += estimate
        model_rows.append({
            "model": model,
            "calls": int(calls),
            "tokens_in": int(tokens_in),
            "tokens_out": int(tokens_out),
            "cached_tokens": int(cached),
            "estimated_cost": None if estimate is None else _round_money(estimate),
        })

    period_days = max(1, (window_end - window_start).days)
    per = lambda denominator: (  # noqa: E731
        None if not denominator else _round_money(estimated_total / denominator)
    )

    return {
        "tenant_id": tenant_id,
        "period": {
            "start": window_start.date().isoformat(),
            # Reported inclusive, because that is how it was asked for.
            "end": (window_end.date() - timedelta(days=1)).isoformat(),
            "days": period_days,
        },
        "calls_by_type": calls_rows,
        "by_model": model_rows,
        "totals": {
            "calls": total_calls,
            "tokens_in": total_in,
            "tokens_out": total_out,
            "cached_tokens": total_cached,
            "errors": total_errors,
            # Our cache, not the provider's: the share of calls answered without
            # a request leaving the process.
            "cache_hit_rate": round(total_hits / total_calls, 4) if total_calls else 0.0,
            "cache_hits": total_hits,
        },
        "estimated_cost": {
            "currency": currency,
            "total": _round_money(estimated_total),
            "per_scan": per(int(scans)),
            "per_insight": per(int(insights)),
            "per_tenant_day": per(period_days),
            "scans_with_model_calls": int(scans),
            "insights_with_model_calls": int(insights),
            "unpriced_models": sorted(set(unpriced)),
            "basis": (
                "List price per 1M tokens from app/llm/rates.yaml. Excludes batch discounts, "
                "free-tier allowances and long-context tiers. An estimate, not an invoice."
            ),
        },
    }


def as_text(report: dict[str, Any]) -> str:
    """The same report as a fixed-width block, ready to paste into a slide.

    Exists because the JSON is the machine's answer and this is the human's, and
    reformatting the JSON by hand at 2am before a demo is how a wrong number
    gets onto a slide.
    """
    period = report["period"]
    totals = report["totals"]
    cost = report["estimated_cost"]
    currency = cost["currency"]
    lines = [
        f"LLM cost -- tenant {report['tenant_id']}, {period['start']} to {period['end']} "
        f"({period['days']} days)",
        "",
        f"{'call type':<24}{'calls':>7}{'tokens in':>12}{'tokens out':>12}{'mean ms':>10}{'errors':>8}",
        "-" * 73,
    ]
    for row in report["calls_by_type"]:
        lines.append(
            f"{row['call_type']:<24}{row['calls']:>7}{row['tokens_in']:>12,}"
            f"{row['tokens_out']:>12,}{row['mean_duration_ms']:>10.1f}{row['errors']:>8}"
        )
    lines += [
        "-" * 73,
        f"{'total':<24}{totals['calls']:>7}{totals['tokens_in']:>12,}{totals['tokens_out']:>12,}"
        f"{'':>10}{totals['errors']:>8}",
        "",
        f"cache hit rate       {totals['cache_hit_rate'] * 100:.1f}%  "
        f"({totals['cache_hits']} of {totals['calls']} calls, agent-side cache)",
        f"provider cached in   {totals['cached_tokens']:,} tokens",
        "",
        f"estimated cost       {currency} {cost['total']:.6f}",
        f"  per scan           {_money_or_dash(cost['per_scan'], currency)}"
        f"   ({cost['scans_with_model_calls']} scans made model calls)",
        f"  per insight        {_money_or_dash(cost['per_insight'], currency)}"
        f"   ({cost['insights_with_model_calls']} insights attributed)",
        f"  per tenant-day     {_money_or_dash(cost['per_tenant_day'], currency)}",
    ]
    if cost["unpriced_models"]:
        lines.append(
            "  NOT PRICED         " + ", ".join(cost["unpriced_models"])
            + " -- no entry in rates.yaml, excluded from the total"
        )
    lines += ["", cost["basis"]]
    return "\n".join(lines)


def _money_or_dash(value: float | None, currency: str) -> str:
    return "--" if value is None else f"{currency} {value:.6f}"
