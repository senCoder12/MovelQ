"""Alert routing: which insights fire which rules, for whom, how loud.

Pure and stateless -- this module never touches a database and never calls
an LLM (alerting is deterministic routing over content that already
exists, so cost per scan stays flat as rules grow). It takes the insight
list the caller has already ranked and deduped (see rank_and_dedupe below)
and the rules from alert_rules.yaml, and returns candidate matches: which
rule fired on which insight, for which persona, at what urgency. Everything
stateful -- cooldown history, suppression, persistence of alert rows -- is
Java's job (ReportDispatchService's sibling here is the Java-side
AlertScanService), since only Java has the alert table to check history
against.

Escalation logic (documented here, enforced by Java on top of these
candidates):
  immediate -> in-app now, badge on the brief
  daily     -> collected into the next brief
  weekly    -> collected into the leadership pack
  An immediate alert unacknowledged after 24h is re-raised once at the next
  scan with a "repeat" flag. Once only -- no infinite escalation.

Cooldown is per (tenant, rule_id, entity) -- the same vendor cannot
re-alert inside its window. That's what keeps this from becoming noise as
more rules are added, and it's worth saying so in the pitch.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_RULES_PATH = Path(__file__).resolve().parent / "alert_rules.yaml"


def load_rules() -> list[dict[str, Any]]:
    return yaml.safe_load(_RULES_PATH.read_text()) or []


def _entity_key(insight: dict[str, Any]) -> tuple[str, str]:
    entity = insight.get("entity", {}) or {}
    return (entity.get("dim", ""), entity.get("id", ""))


def rank_and_dedupe(insights: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sorted by severity desc; at most one insight survives per
    (metric_id, entity_dim, entity_id) -- the highest-severity one. Two
    insights sharing a metric AND an entity are the same finding reported
    twice (a re-detected or near-duplicate signal), not two different
    entities under the same metric, which is exactly what r_new_bad_entity
    exists to catch and must not be deduped away.

    Rules evaluate strictly after this, so a deduped child insight can
    never fire its own alert -- only the surviving parent can.
    """
    best_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    for insight in insights:
        metric_id = insight.get("metric", {}).get("id", "")
        dim, entity_id = _entity_key(insight)
        key = (metric_id, dim, entity_id)
        current = best_by_key.get(key)
        if current is None or insight.get("severity", 0) > current.get("severity", 0):
            best_by_key[key] = insight
    return sorted(best_by_key.values(), key=lambda i: i.get("severity", 0), reverse=True)


def _matches_metric(rule: dict[str, Any], insight: dict[str, Any]) -> bool:
    metric_id = rule.get("metric_id", "*")
    return metric_id == "*" or metric_id == insight.get("metric", {}).get("id")


def _passes_min_sample(rule: dict[str, Any], insight: dict[str, Any]) -> bool:
    n = insight.get("metric", {}).get("n", 0)
    return n >= rule.get("min_sample", 0)


def _severity_gte(rule: dict[str, Any], insight: dict[str, Any]) -> bool:
    return insight.get("severity", 0) >= rule["threshold"]


def _sla_breach(rule: dict[str, Any], insight: dict[str, Any]) -> bool:
    """An insight carries an SLA breach if any of its references is
    explicitly typed "sla" -- the schema supports this reference type, but
    no current detector emits one, so this rule is real but dormant against
    today's mock data. That's an honest state, not a bug: it will start
    firing the day a detector cites an SLA reference."""
    return any(ref.get("type") == "sla" for ref in insight.get("references", []))


def _delta_pp_gte(rule: dict[str, Any], insight: dict[str, Any]) -> bool:
    """Gap below full coverage for a coverage-shaped metric: 100 -
    metric.value >= threshold percentage points. A generic proxy for
    "baseline-adjusted coverage shortfall" -- the InsightPacket schema has
    no separate "expected" field to diff against, so 100% coverage is the
    one expectation every tenant can be held to regardless of segment."""
    value = insight.get("metric", {}).get("value", 0)
    return (100 - value) >= rule["threshold"]


def _reconciliation_gap_gte(rule: dict[str, Any], insight: dict[str, Any]) -> bool:
    """The metric's own value, read directly as a gap percentage, exceeds
    threshold -- for a detector whose metric.value already *is* "percent
    of trips with a reconciliation gap" (delay_reconciliation_gap is the
    example), this is a plainer read than severity_gte."""
    value = insight.get("metric", {}).get("value", 0)
    return value >= rule["threshold"]


def _persistence_weeks_gte(rule: dict[str, Any], insight: dict[str, Any]) -> bool:
    """Not wired up: persistence across scan weeks needs a history this
    stateless module deliberately does not keep (see module docstring --
    that's Java's job). No seed rule uses this condition; it is here so the
    condition vocabulary in alert_rules.yaml is fully real rather than
    partly decorative. Always false until a caller supplies real history."""
    return False


_CONDITION_EVALUATORS = {
    "severity_gte": _severity_gte,
    "sla_breach": _sla_breach,
    "delta_pp_gte": _delta_pp_gte,
    "reconciliation_gap_gte": _reconciliation_gap_gte,
    "persistence_weeks_gte": _persistence_weeks_gte,
}


def evaluate(
    insights: list[dict[str, Any]],
    known_entities: set[tuple[str, str]] | None = None,
    rules: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Every (rule, insight) pair that matches, as a candidate dict:
    {rule_id, insight_id, persona, urgency, channel, entity_dim,
    entity_value, cooldown_hours}. `insights` must already be ranked and
    deduped (see rank_and_dedupe) -- this function does not do that itself,
    so a caller that forgets to dedupe will get one alert per duplicate.

    Java applies cooldown and suppression on top of whatever this returns,
    then persists whichever candidates survive.

    `known_entities` -- every (entity_dim, entity_id) pair that has ever
    fired an alert before, for the new_entity condition. Supplied by the
    caller: Java has the alert history, this module keeps none of its own.
    """
    rules = load_rules() if rules is None else rules
    known_entities = known_entities or set()
    candidates: list[dict[str, Any]] = []

    for insight in insights:
        dim, entity_id = _entity_key(insight)
        for rule in rules:
            if not _matches_metric(rule, insight) or not _passes_min_sample(rule, insight):
                continue

            condition = rule["condition"]
            if condition == "new_entity":
                matched = (dim, entity_id) not in known_entities
            else:
                evaluator = _CONDITION_EVALUATORS.get(condition)
                matched = bool(evaluator and evaluator(rule, insight))
            if not matched:
                continue

            candidates.append(
                {
                    "rule_id": rule["id"],
                    "insight_id": insight["insight_id"],
                    "persona": rule["persona"],
                    "urgency": rule["urgency"],
                    "channel": rule["channel"],
                    "entity_dim": dim,
                    "entity_value": entity_id,
                    "cooldown_hours": rule.get("cooldown_hours", 24),
                }
            )

    return candidates
