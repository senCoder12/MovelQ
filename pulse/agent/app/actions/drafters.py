"""Action drafters -- the "act" third of sense-reason-act.

Each drafter maps one InsightPacket to zero or more action drafts. The agent
never executes anything here: `draft_action` returns a subject/body/preview
for Java to persist and a human to approve or reject -- see
agent/app/api/actions.py for the LLM/validate/retry/fallback pipeline this
module feeds.

Every drafter here computes the *structured* half of a draft (recipient,
title, rationale, preview, facts_cited) itself, deterministically, from
fields already present on the insight -- only `subject`/`body` are free
prose, normally written by the LLM and validated against the insight before
being trusted (agent/app/agent/validator.py:validate_action). The fallback
prose below is built the same way facts_cited is: string-interpolated
straight from grounded fields, so it can never fail that validation itself.

ESCORT_COVERAGE_REVIEW is deliberately exclusive of VENDOR_ESCALATION even
though escort_coverage_night_female carries vendor attribution: the two
reads are not the same finding (a coverage gap that targeting is *closing*,
not a vendor failing an SLA), and the coverage-gap framing must not be
diluted by a second, more adversarial draft over the same numbers.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Callable

from app.agent import validator
from app.agent.json_llm import parse_json_object
from app.config import get_settings
from app.llm import client as llm_client

ACTION_TYPES = ("VENDOR_ESCALATION", "SYSTEM_AUDIT_REQUEST", "ESCORT_COVERAGE_REVIEW", "BILLING_RECONCILIATION")

_DELAY_RECONCILIATION_METRIC = "delay_reconciliation_gap"
_ESCORT_COVERAGE_METRIC = "escort_coverage_night_female"
_BILLING_METRICS = {"ev_contract_mismatch_rate", "unbilled_km_rate"}

# Always a relative window, never a calendar date: a date both overreaches
# the sender's authority to set a deadline and introduces a number the
# InsightPacket cannot ground (see module docstring on validate_action).
_RESPONSE_WINDOW = "by the end of next week"

_PROMPT_PATH = Path(__file__).resolve().parents[1] / "agent" / "prompts" / "draft_action.md"


# --- InsightPacket field lookups --------------------------------------------

def _metric(insight: dict[str, Any]) -> dict[str, Any]:
    return insight.get("metric", {}) or {}


def _impact(insight: dict[str, Any]) -> dict[str, Any]:
    return insight.get("impact", {}) or {}


def _vendor_attributions(insight: dict[str, Any]) -> list[dict[str, Any]]:
    vendors = [a for a in insight.get("attribution", []) if a.get("dim") == "vendor_id"]
    return sorted(vendors, key=lambda a: a.get("contribution_pct", 0), reverse=True)


def _top_vendor(insight: dict[str, Any]) -> dict[str, Any] | None:
    vendors = _vendor_attributions(insight)
    return vendors[0] if vendors else None


def _reference_by_label(insight: dict[str, Any], needle: str) -> dict[str, Any] | None:
    needle = needle.lower()
    for ref in insight.get("references", []):
        if needle in ref.get("label", "").lower():
            return ref
    return None


def _control_by_name(insight: dict[str, Any], name: str) -> dict[str, Any] | None:
    for control in insight.get("controls", []):
        if control.get("control") == name:
            return control
    return None


def _num(value: Any) -> str:
    """Render a number exactly as given -- no rounding, no re-derivation --
    so it always round-trips through validate_action. Ints get comma
    grouping; floats print as Python already renders them (1.38, 60.8, ...),
    which is also what json.dumps would have written them as."""
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return f"{value:,}"
    return f"{value}"


def _money(value: float) -> str:
    """₹ at business-register width: crore / lakh / million, matching the
    suffixes agent/app/agent/validator.py already expands."""
    if abs(value) >= 10_000_000:
        return f"₹{value / 10_000_000:g}Cr"
    if abs(value) >= 1_000_000:
        return f"₹{value / 1_000_000:g}M"
    if abs(value) >= 100_000:
        return f"₹{value / 100_000:g}L"
    return f"₹{_num(value)}"


def _control_text(control: dict[str, Any]) -> str:
    sign = "+" if control["gap_pp"] >= 0 else ""
    survives = "survives" if control["survives"] else "explained away"
    return f"{sign}{_num(control['gap_pp'])}pp ({survives})"


def _preview(action_type: str) -> dict[str, Any]:
    channel_noun = {
        "VENDOR_ESCALATION": "email is actually sent to the vendor",
        "SYSTEM_AUDIT_REQUEST": "ticket is actually filed with the platform team",
        "ESCORT_COVERAGE_REVIEW": "note is actually sent to the vendors",
        "BILLING_RECONCILIATION": "note is actually sent to finance",
    }[action_type]
    return {
        "what_changes": f"Approving records the decision to an approval log; no {channel_noun}.",
        "reversible": True,
    }


# --- Applicability -----------------------------------------------------------

def applicable_action_types(insight: dict[str, Any]) -> list[str]:
    """Which action types this insight supports, in the order buttons render."""
    metric_id = _metric(insight).get("id")

    if metric_id == _ESCORT_COVERAGE_METRIC:
        return ["ESCORT_COVERAGE_REVIEW"]
    if metric_id in _BILLING_METRICS:
        return ["BILLING_RECONCILIATION"]

    types: list[str] = []
    if _top_vendor(insight) is not None:
        types.append("VENDOR_ESCALATION")
    if metric_id == _DELAY_RECONCILIATION_METRIC:
        types.append("SYSTEM_AUDIT_REQUEST")
    return types


# --- Per-type context builders ------------------------------------------------
# Each returns: recipient, channel, title, subject, body_fallback, facts_cited,
# rationale. Only subject/body are ever handed to the LLM as a starting point;
# everything else here is the deterministic, already-grounded structure.

def _vendor_escalation(insight: dict[str, Any]) -> dict[str, Any]:
    vendor = _top_vendor(insight)
    if vendor is None:
        raise ValueError("VENDOR_ESCALATION requires a vendor_id attribution")
    reported = _reference_by_label(insight, "mean reported delay_minutes")
    computed = _reference_by_label(insight, "mean computed_arrival_delay_min")
    vendor_control = _control_by_name(insight, "vendor")

    facts_cited = [
        {"label": "Vendor", "value": vendor["value"], "source_field": "attribution[dim=vendor_id].value"},
        {"label": "Trips attributed to this vendor", "value": _num(vendor["n"]),
         "source_field": "attribution[dim=vendor_id].n"},
        {"label": "Share of the fleet-wide contradiction", "value": f"{_num(vendor['contribution_pct'])}%",
         "source_field": "attribution[dim=vendor_id].contribution_pct"},
    ]
    if reported is not None:
        facts_cited.append({"label": "Mean reported delay (vendor-submitted)",
                             "value": f"{_num(reported['value'])} minutes", "source_field": "references[].value"})
    if computed is not None:
        facts_cited.append({"label": "Mean computed arrival delay (observed)",
                             "value": f"{_num(computed['value'])} minutes", "source_field": "references[].value"})
    if vendor_control is not None:
        facts_cited.append({"label": "Gap remaining after controlling for vendor",
                             "value": _control_text(vendor_control), "source_field": "controls[control=vendor]"})

    delay_clause = (
        f", the average reported delay is {_num(reported['value'])} minutes against a computed average "
        f"arrival delay of {_num(computed['value'])} minutes."
        if reported is not None and computed is not None
        else "."
    )
    body_lines = [
        f"We are writing to flag a discrepancy between reported and observed delay figures on trips "
        f"operated by {vendor['value']}.",
        "",
        f"Under the reporting terms of the contract, delay_minutes is expected to reflect the actual "
        f"arrival delay for each trip. Across {_num(vendor['n'])} trips attributed to {vendor['value']} "
        f"({_num(vendor['contribution_pct'])}% of the fleet-wide contradiction we are tracking this period)"
        f"{delay_clause}",
    ]
    if vendor_control is not None:
        body_lines.append(
            f"This gap persists after controlling for vendor assignment ({_control_text(vendor_control)}), "
            f"so it does not appear to be explained by which trips this vendor happens to run."
        )
    body_lines += [
        "",
        "We are unable to confirm the cause from our side and would appreciate your team's read on where "
        "the reporting gap originates -- for example, whether delay_minutes is being populated at the "
        "point of dispatch for these trips.",
        "",
        f"The underlying trip-level data is available on request. We would appreciate a response "
        f"{_RESPONSE_WINDOW}.",
    ]

    return {
        "recipient": {"role": "vendor_account_manager", "name": vendor["value"]},
        "channel": "email",
        "title": f"Escalate delay reporting gap to {vendor['value']}",
        "subject": f"Delay reporting discrepancy -- {vendor['value']}, {_num(vendor['n'])} trips",
        "body_fallback": "\n".join(body_lines),
        "facts_cited": facts_cited,
        "rationale": (
            f"{vendor['value']} accounts for {_num(vendor['contribution_pct'])}% of this contradiction "
            f"({_num(vendor['n'])} trips) and the gap survives a vendor control -- concentrated enough to "
            "raise with the vendor directly."
        ),
    }


def _system_audit_request(insight: dict[str, Any]) -> dict[str, Any]:
    cohort = next((a for a in insight.get("attribution", []) if a.get("dim") == "shift_suffix"), None)
    nonzero = _reference_by_label(insight, "nonzero reported delay_minutes")
    vendor_span = _reference_by_label(insight, "distinct vendors")
    hour_control = _control_by_name(insight, "hour_of_day")
    vendor_control = _control_by_name(insight, "vendor")
    cohort_label = cohort["value"] if cohort else "the affected"

    facts_cited: list[dict[str, str]] = []
    if cohort is not None:
        facts_cited.append({"label": f"Trips within '{cohort['value']}' shift-code cohort",
                             "value": _num(cohort["n"]), "source_field": "attribution[dim=shift_suffix].n"})
    if nonzero is not None:
        facts_cited.append({"label": "Trips in that cohort with nonzero reported delay_minutes",
                             "value": _num(nonzero["value"]), "source_field": "references[].value"})
    if hour_control is not None:
        facts_cited.append({"label": "Gap remaining after controlling for hour of day",
                             "value": _control_text(hour_control), "source_field": "controls[control=hour_of_day]"})
    if vendor_control is not None:
        vendor_value = _control_text(vendor_control)
        if vendor_span is not None:
            vendor_value += f", spans {_num(vendor_span['value'])} vendors"
        facts_cited.append({"label": "Gap remaining after controlling for vendor",
                             "value": vendor_value, "source_field": "controls[control=vendor]"})
    facts_cited.append({"label": "Start date of the pattern", "value": "not inferable from available fields",
                         "source_field": "data_quality"})

    evidence_lines = []
    if cohort is not None and nonzero is not None:
        evidence_lines.append(
            f"- Of {_num(cohort['n'])} trips in the '{cohort['value']}' cohort, only {_num(nonzero['value'])} "
            f"have a nonzero reported delay_minutes value."
        )
    if hour_control is not None:
        evidence_lines.append(f"- The gap survives a control for hour of day ({_control_text(hour_control)}).")
    if vendor_control is not None:
        span_clause = f", across all {_num(vendor_span['value'])} vendors represented in that control" if vendor_span else ""
        evidence_lines.append(f"- The gap survives a control for vendor{span_clause} ({_control_text(vendor_control)}).")
    evidence_lines.append("- We are unable to infer a start date for this pattern from the fields available to us.")

    body_lines = [
        f"This is a request to audit the scheduling/write path for '{cohort_label}' shift-type codes, not a "
        "conclusion.",
        "",
        f"Hypothesis, not yet confirmed: the scheduling path for '{cohort_label}' shift codes never writes "
        "the delay_minutes field, rather than those trips genuinely running on time.",
        "",
        "Evidence:",
        *evidence_lines,
        "",
        f"What would confirm it: source-system write logs for the '{cohort_label}' scheduling path, showing "
        "whether delay_minutes is ever populated for these trips at write time.",
        "",
        "We would appreciate the platform team's read on this within the next two weeks.",
    ]

    return {
        "recipient": {"role": "platform_team", "name": "Platform team"},
        "channel": "ticket",
        "title": f"Audit request: '{cohort_label}' shift-code delay-capture gap",
        "subject": f"Audit request: '{cohort_label}' shift-code delay-capture gap",
        "body_fallback": "\n".join(body_lines),
        "facts_cited": facts_cited,
        "rationale": (
            f"The '{cohort_label}' cohort carries the bulk of the contradiction and the gap survives both "
            "hour-of-day and vendor controls, which rules out the obvious confounds -- only a look at the "
            "write path can confirm the mechanism."
        ),
    }


def _escort_coverage_review(insight: dict[str, Any]) -> dict[str, Any]:
    metric = _metric(insight)
    impact = _impact(insight)
    baseline = _reference_by_label(insight, "baseline escort rate")
    vendors = _vendor_attributions(insight)[:2]

    facts_cited = [
        {"label": "Coverage in this segment", "value": f"{_num(metric['value'])}%", "source_field": "metric.value"},
        {"label": "Legs scanned in this segment", "value": _num(metric["n"]), "source_field": "metric.n"},
    ]
    if impact.get("affected_trips") is not None:
        facts_cited.append({"label": "Uncovered legs", "value": _num(impact["affected_trips"]),
                             "source_field": "impact.affected_trips"})
    if baseline is not None:
        facts_cited.append({"label": "Baseline escort rate across all legs", "value": f"{_num(baseline['value'])}%",
                             "source_field": "references[].value"})
    for vendor in vendors:
        facts_cited.append({"label": "Vendor", "value": vendor["value"],
                             "source_field": "attribution[dim=vendor_id].value"})
        facts_cited.append({"label": f"{vendor['value']} share of uncovered legs",
                             "value": f"{_num(vendor['contribution_pct'])}% ({_num(vendor['n'])} legs)",
                             "source_field": "attribution[dim=vendor_id]"})

    vendor_clause = ""
    if vendors:
        names = " and ".join(v["value"] for v in vendors)
        shares = " and ".join(f"{_num(v['contribution_pct'])}%" for v in vendors)
        vendor_clause = (
            f"\n\n{names} account for the largest shares of the uncovered legs, at {shares} of their "
            "respective allocations. We are asking both vendors to review escort resourcing for night, "
            "female-employee legs, and are separately raising a resourcing request on our side to close "
            "the remaining gap."
        )

    baseline_clause = ""
    if baseline is not None:
        baseline_clause = (
            f" That coverage rate is roughly double the {_num(baseline['value'])}% baseline escort rate "
            "across all legs, so targeting toward this segment appears to be working; the gap is that it "
            "has plateaued short of full coverage rather than closed."
        )

    body = (
        "This is a note on night-time escort coverage for female employees, framed as a coverage gap "
        "rather than a compliance breach -- we do not hold the underlying policy document, so we make no "
        "claim either way about it.\n\n"
        f"Coverage for this segment currently stands at {_num(metric['value'])}% across {_num(metric['n'])} "
        f"legs scanned this period, leaving {_num(impact.get('affected_trips'))} legs without an escort."
        f"{baseline_clause}"
        f"{vendor_clause}\n\n"
        f"We would appreciate a response {_RESPONSE_WINDOW}."
    )

    return {
        "recipient": {
            "role": "vendor_account_manager",
            "name": " & ".join(v["value"] for v in vendors) if vendors else "Fleet vendors",
        },
        "channel": "email",
        "title": "Escort coverage gap -- night, female employees",
        "subject": "Night escort coverage, female employees -- coverage gap, not a compliance finding",
        "body_fallback": body,
        "facts_cited": facts_cited,
        "rationale": (
            "Coverage has plateaued below full despite strong targeting, concentrated at a small number of "
            "vendors -- close enough to name them and ask for a resourcing plan."
        ),
    }


def _billing_reconciliation(insight: dict[str, Any]) -> dict[str, Any]:
    metric = _metric(insight)
    impact = _impact(insight)
    expected = _reference_by_label(insight, "expected") or _reference_by_label(insight, "unbilled")
    affected = impact.get("affected_trips")
    cost = impact.get("cost_inr_month")
    entity_name = insight.get("entity", {}).get("name", "the contract")

    facts_cited = [{"label": "Rows scanned this period", "value": _num(metric.get("n")), "source_field": "metric.n"}]
    if affected is not None:
        facts_cited.append({"label": "Rows affected", "value": f"{_num(affected)} ({_num(metric.get('value'))}%)",
                             "source_field": "impact.affected_trips"})
    if cost is not None:
        facts_cited.append({"label": "Monthly billing exposure", "value": _money(cost),
                             "source_field": "impact.cost_inr_month"})
    if expected is not None:
        facts_cited.append({"label": "Contracted expectation", "value": str(expected["value"]),
                             "source_field": "references[].value"})

    mismatch_clause = "."
    if affected is not None:
        expectation_clause = f" ({expected['value']})" if expected is not None else ""
        mismatch_clause = (
            f", {_num(affected)} ({_num(metric.get('value'))}%) do not match the contracted "
            f"expectation{expectation_clause}."
        )
    cost_clause = f" That represents a monthly billing exposure of {_money(cost)}." if cost is not None else ""

    body = (
        "This is a request to reconcile billing against actual figures before the next billing cycle.\n\n"
        f"Of {_num(metric.get('n'))} rows scanned this period{mismatch_clause}{cost_clause}\n\n"
        "We are unable to confirm from our side whether these rows reflect a genuine mismatch or a data- "
        "or contract-mapping issue -- we would ask finance to reconcile contract terms against actual "
        "figures for the affected rows before the next billing cycle closes.\n\n"
        f"The affected row list is available on request. We would appreciate a response {_RESPONSE_WINDOW}."
    )

    title = f"Reconcile {entity_name} billing"
    if affected is not None:
        title += f" -- {_num(affected)} affected rows"

    return {
        "recipient": {"role": "finance_team", "name": "Finance team"},
        "channel": "email",
        "title": title,
        "subject": f"Billing reconciliation -- {entity_name}" + (f", {_num(affected)} rows" if affected is not None else ""),
        "body_fallback": body,
        "facts_cited": facts_cited,
        "rationale": (
            "A direct, quantifiable billing exposure with a small, enumerable set of affected rows -- "
            "reconciliation is mechanical, not investigative."
        ),
    }


_BUILDERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "VENDOR_ESCALATION": _vendor_escalation,
    "SYSTEM_AUDIT_REQUEST": _system_audit_request,
    "ESCORT_COVERAGE_REVIEW": _escort_coverage_review,
    "BILLING_RECONCILIATION": _billing_reconciliation,
}


# --- LLM authoring, validated, with a grounded fallback -----------------------

def _prompt_template() -> str:
    return _PROMPT_PATH.read_text()


def _call_llm(insight: dict[str, Any], action_type: str, context: dict[str, Any],
              feedback: str | None = None) -> dict[str, Any] | None:
    if not get_settings().llm_enabled:
        # Declared degraded mode: _author falls through to the templated
        # body_fallback built from facts_cited, at confidence "low".
        return None
    payload = {
        "type": action_type,
        "insight": insight,
        "recipient": context["recipient"],
        "facts_cited": context["facts_cited"],
    }
    prompt = _prompt_template() + "\n\n## Input\n\n" + json.dumps(payload, indent=2, default=str)
    if feedback:
        prompt += f"\n\n## Correction required\n\n{feedback}"
    try:
        raw = llm_client.complete(
            system="Respond with strict JSON only, no markdown fences.",
            prompt=prompt,
            call_type="draft_action",
        )
    except Exception:
        # Missing key, network failure, rate limit -- degrade to the fallback
        # rather than a 500. See module docstring.
        return None
    return parse_json_object(raw)


def _grounded(insight: dict[str, Any], parsed: dict[str, Any] | None) -> tuple[str, str, list[float]] | None:
    """None if the parse was empty/malformed; otherwise (subject, body,
    ungrounded numbers) -- an empty ungrounded list means it passed."""
    if parsed is None:
        return None
    subject, body = str(parsed.get("subject", "")), str(parsed.get("body", ""))
    if not subject or not body:
        return None
    result = validator.validate_action(insight, subject, body)
    return subject, body, sorted(result.ungrounded)


def _author(insight: dict[str, Any], action_type: str, context: dict[str, Any]) -> tuple[str, str, str]:
    first = _grounded(insight, _call_llm(insight, action_type, context))
    if first is not None:
        subject, body, ungrounded = first
        if not ungrounded:
            return subject, body, "high"

        feedback = (
            "Your previous draft used numbers that do not appear in the source insight "
            f"({ungrounded}). Regenerate, citing only numbers present in the insight data below."
        )
        retry = _grounded(insight, _call_llm(insight, action_type, context, feedback=feedback))
        if retry is not None:
            subject, body, ungrounded = retry
            if not ungrounded:
                return subject, body, "medium"

    return context["subject"], context["body_fallback"], "low"


def draft_action(insight: dict[str, Any], action_type: str) -> dict[str, Any]:
    """Draft one action. Raises ValueError if `action_type` is unknown or
    does not apply to `insight` -- callers (agent/app/api/actions.py) turn
    that into a 400, never a 500."""
    if action_type not in ACTION_TYPES:
        raise ValueError(f"unknown action type: {action_type}")
    if action_type not in applicable_action_types(insight):
        raise ValueError(f"{action_type} does not apply to insight {insight.get('insight_id')}")

    context = _BUILDERS[action_type](insight)
    subject, body, confidence = _author(insight, action_type, context)

    return {
        "action_id": f"act_{uuid.uuid4().hex[:12]}",
        "insight_id": insight["insight_id"],
        "type": action_type,
        "title": context["title"],
        "recipient": context["recipient"],
        "channel": context["channel"],
        "subject": subject,
        "body": body,
        "facts_cited": context["facts_cited"],
        "preview": _preview(action_type),
        "rationale": context["rationale"],
        "confidence": confidence,
    }
