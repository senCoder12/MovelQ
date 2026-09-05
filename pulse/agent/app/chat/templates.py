"""One hand-written answer per intent.

These do string substitution, not generation. The prose is written here, in
full, and the packet's values are slotted into it -- so an answer cannot cite
a number the insight does not carry, cannot round one differently, and reads
the same on the thirtieth question as on the first.

Every answer returns the same shape:

    {"intent", "answer", "evidence": [...], "table": ... | None, "followups": [...]}

``evidence`` is the trace pattern applied to conversation: each row names the
figure, its value, and the packet field it came from, so a claim in the prose
can be checked against the field beside it without leaving the drawer.

Two intents may optionally have their prose re-phrased by a model --
WHY_THIS_DIMENSION, which compares several attribution entries, and
WHAT_SHOULD_I_DO, which connects a standing recommendation to what was just
asked. Both re-phrase an answer this module already wrote, both must pass
app/agent/validator.py against the packet, both fall back to the template on
any failure, and both are skipped entirely when pulse.llm.enabled is false.
No other intent ever reaches a model.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from app.agent import validator
from app.agent.json_llm import parse_json_object
from app.chat import facts as chat_facts
from app.chat import intents
from app.config import get_settings
from app.llm import client as llm_client

_PROMPT_PATH = Path(__file__).resolve().parents[1] / "agent" / "prompts" / "phrase_answer.md"

#: Attribution entries named when an answer lists alternatives. Three is what
#: fits in a sentence a reader will actually finish.
_MAX_ALTERNATIVES = 3


# --- rendering helpers --------------------------------------------------------

def _n(value: Any) -> str:
    """Render a number exactly as the packet carries it -- comma grouping for
    ints, floats printed as Python already renders them. Never re-round: a
    figure that does not round-trip through app/agent/validator.py is a figure
    the answer had no right to say."""
    if isinstance(value, bool) or value is None:
        return str(value)
    if isinstance(value, int):
        return f"{value:,}"
    return f"{value}"


def _pp(value: Any) -> str:
    """A gap in percentage points, always signed, so "+14.6pp" and "-2.0pp"
    read the same way round."""
    if value is None:
        return "n/a"
    return f"{'+' if value >= 0 else ''}{_n(value)}pp"


def _row(label: str, value: Any, source_field: str) -> dict[str, str]:
    return {"label": label, "value": _n(value) if not isinstance(value, str) else value,
            "source_field": source_field}


def _facts(insight: dict[str, Any]) -> dict[str, Any]:
    return insight.get("chat_facts") or {"available": False, "reason": "no chat facts were computed"}


def _metric(insight: dict[str, Any]) -> dict[str, Any]:
    return insight.get("metric") or {}


def _target_pct(insight: dict[str, Any]) -> float | None:
    for reference in insight.get("references") or []:
        if reference.get("type") == "sla":
            return reference.get("value")
    return (_facts(insight).get("sample") or {}).get("target_pct")


def _adverse_rows(insight: dict[str, Any]) -> int | None:
    return (insight.get("impact") or {}).get("affected_trips")


def _answer(
    intent: str,
    answer: str,
    evidence: list[dict[str, str]],
    followups: list[str],
    table: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "intent": intent,
        "answer": answer,
        "evidence": evidence,
        "table": table,
        "followups": followups,
    }


def _degraded(intent: str, facts: dict[str, Any], what: str) -> dict[str, Any]:
    """The honest answer when the enrichment could not be computed. Says what
    is missing and why, and offers the questions that only need the packet."""
    return _answer(
        intent,
        f"I can't answer that here: {what} needs figures that could not be recomputed "
        f"for this insight ({facts.get('reason') or 'reason not recorded'}). "
        "I can still answer from what the insight itself carries.",
        [_row("Enrichment", "unavailable", "chat_facts.available")],
        ["What do you recommend?", "When did this begin?"],
    )


# --- WHY_THIS_DIMENSION -------------------------------------------------------

def why_this_dimension(insight: dict[str, Any], slots: dict[str, Any]) -> dict[str, Any]:
    facts = _facts(insight)
    ranked = facts.get("attribution_ranked") or []
    if not facts.get("available") or not ranked:
        return _degraded("WHY_THIS_DIMENSION", facts, "comparing dimensions")

    target = _target_pct(insight)
    top = ranked[0]

    # One entry per dimension -- its strongest slice -- so the comparison is
    # between dimensions rather than between five slices of the same one.
    best_per_dim: dict[str, dict[str, Any]] = {}
    for entry in ranked:
        best_per_dim.setdefault(entry["dim"], entry)
    alternatives = [e for e in best_per_dim.values() if e["dim"] != top["dim"]][: _MAX_ALTERNATIVES - 1]

    lines = [
        f"Because that is where the adverse rows actually sit. {top['value']} "
        f"({top['dim_label']}) carries {_n(top['contribution_pct'])}% of the "
        f"{_n(_adverse_rows(insight))} rows behind this finding, at "
        f"{_n(top['rate_pct'])}% against a {_n(target)}% target -- {_pp(top['gap_pp'])} past it, "
        f"across {_n(top['n'])} rows."
    ]
    if alternatives:
        compared = "; ".join(
            f"the worst {e['dim_label']} is {e['value']} at {_n(e['contribution_pct'])}% "
            f"({_n(e['rate_pct'])}%)"
            for e in alternatives
        )
        lines.append(
            f"Ranked against the other dimensions we slice this metric by: {compared}. "
            f"{top['value']} leads all {_n(top['slices_ranked'])} slices we ranked."
        )

    vendor = chat_facts.control_for(facts, "vendor")
    if vendor is not None and vendor["all_hold"]:
        lines.append(
            f"It is not the vendor: the gap holds inside every one of the "
            f"{_n(vendor['n_entities'])} vendors tested individually, mean "
            f"{_pp(vendor['mean_gap_pp'])}, so vendor mix cannot be what produces it."
        )
    elif vendor is not None:
        lines.append(
            f"Vendor explains part of it but not the shape: the gap still holds inside "
            f"{_n(vendor['n_holding'])} of {_n(vendor['n_entities'])} vendors tested "
            f"individually, mean {_pp(vendor['mean_gap_pp'])}."
        )

    evidence = [
        _row(f"Top slice ({top['dim_label']})", top["value"], "attribution[0].value"),
        _row("Share of adverse rows", f"{_n(top['contribution_pct'])}%", "attribution[0].contribution_pct"),
        _row("Rate in that slice", f"{_n(top['rate_pct'])}%", "chat_facts.attribution_ranked[0].rate_pct"),
        _row("Gap past target", _pp(top["gap_pp"]), "chat_facts.attribution_ranked[0].gap_pp"),
        _row("Slices ranked", top["slices_ranked"], "chat_facts.attribution_ranked"),
    ]
    for entry in alternatives:
        evidence.append(
            _row(
                f"Worst {entry['dim_label']}",
                f"{entry['value']} -- {_n(entry['contribution_pct'])}% of adverse rows",
                f"chat_facts.attribution_ranked[dim={entry['dim']}]",
            )
        )
    if vendor is not None:
        evidence.append(
            _row(
                "Gap within each vendor",
                f"{_n(vendor['n_holding'])} of {_n(vendor['n_entities'])} hold, mean {_pp(vendor['mean_gap_pp'])}",
                "chat_facts.controls_detail[control=vendor_id]",
            )
        )

    return _answer(
        "WHY_THIS_DIMENSION",
        " ".join(lines),
        evidence,
        ["Couldn't this just be the vendor?", "Show me some of these trips", "Is the sample large enough?"],
    )


# --- IS_SAMPLE_SUFFICIENT -----------------------------------------------------

def is_sample_sufficient(insight: dict[str, Any], slots: dict[str, Any]) -> dict[str, Any]:
    facts = _facts(insight)
    sample = facts.get("sample") or {}
    metric = _metric(insight)

    if not sample:
        return _answer(
            "IS_SAMPLE_SUFFICIENT",
            f"{_n(metric.get('n'))} rows went into this figure. I can't compare that to the "
            "metric's declared minimum here -- the registry entry could not be read for this "
            "insight -- so treat the sample size as reported, not as checked.",
            [_row("Rows evaluated", metric.get("n"), "metric.n")],
            ["What if the excluded rows change this?", "Couldn't this just be the vendor?"],
        )

    lines = [
        f"{_n(sample['n'])} rows, against a minimum of {_n(sample['min_sample'])} for this "
        f"metric -- {_n(sample['times_min_sample'])}x the floor."
    ]
    if sample.get("robust_z") is not None:
        lines.append(
            f"The window sits at {_n(sample['value_pct'])}% against a {_n(sample['target_pct'])}% "
            f"target, {_pp(sample['gap_pp'])} past it, which is {_n(sample['robust_z'])} robust "
            f"standard deviations of this metric's own daily spread "
            f"({_n(sample['robust_sigma_pp'])}pp, measured across {_n(sample['daily_points'])} "
            f"daily points, median {_n(sample['daily_median_pct'])}%)."
        )
        lines.append(
            "At this sample size, and that far outside the range the metric normally moves in, "
            "the gap is not attributable to noise."
        )
    else:
        lines.append(
            f"The window sits at {_n(sample['value_pct'])}% against a {_n(sample['target_pct'])}% "
            f"target, {_pp(sample['gap_pp'])} past it. The daily series is too flat to give that "
            "a spread to measure against, so the sample size is the whole of the claim."
        )

    evidence = [
        _row("Rows evaluated", sample["n"], "metric.n"),
        _row("Registry minimum", sample["min_sample"], "chat_facts.sample.min_sample"),
        _row("Window value", f"{_n(sample['value_pct'])}%", "metric.value"),
        _row("Target", f"{_n(sample['target_pct'])}%", "references[type=sla].value"),
        _row("Gap past target", _pp(sample["gap_pp"]), "chat_facts.sample.gap_pp"),
    ]
    if sample.get("robust_z") is not None:
        evidence.append(_row("Robust deviations from target", sample["robust_z"], "chat_facts.sample.robust_z"))
        evidence.append(
            _row("Daily spread (robust SD)", f"{_n(sample['robust_sigma_pp'])}pp",
                 "chat_facts.sample.robust_sigma_pp")
        )
    evidence.append(_row("Daily points", sample["daily_points"], "chat_facts.sample.daily_points"))

    return _answer(
        "IS_SAMPLE_SUFFICIENT",
        " ".join(lines),
        evidence,
        ["What if the excluded rows change this?", "Couldn't this just be the vendor?", "When did this begin?"],
    )


# --- CONTROL_CHALLENGE --------------------------------------------------------

def control_challenge(insight: dict[str, Any], slots: dict[str, Any]) -> dict[str, Any]:
    facts = _facts(insight)
    name = slots.get("control_name") or "other"
    control = chat_facts.control_for(facts, name) if facts.get("available") else None
    tested = chat_facts.tested_control_labels(facts)

    if control is None:
        # Never claim a control that was not run. Name what was.
        offered = ", ".join(tested) if tested else "none, for this insight"
        subject = "that" if name == "other" else name
        return _answer(
            "CONTROL_CHALLENGE",
            f"I can't rule {subject} out, because it was not tested as a control for this "
            f"metric. The controls that were run, each holding one dimension fixed and "
            f"re-checking the gap inside every value of it: {offered}. Ask about one of "
            "those and I can tell you whether the gap survives it.",
            [_row("Control requested", name, "slots.control_name"),
             _row("Controls run", offered, "chat_facts.controls_detail")],
            ["Couldn't this just be the vendor?", "Why this dimension and not another?"],
        )

    label = control["dim_label"]
    loo = control.get("leave_one_out_gap_pp")

    if control["all_hold"]:
        lines = [
            f"No. The gap holds within every {label} tested individually -- all "
            f"{_n(control['n_entities'])} of them, mean gap {_pp(control['mean_gap_pp'])}, "
            f"narrowest {_pp(control['min_gap_pp'])}.",
            f"If this were {label} mix, controlling for {label} would collapse the effect. "
            "It does not.",
        ]
    elif control["n_holding"] > 0:
        lines = [
            f"Partly, but not enough to explain it away. The gap still holds inside "
            f"{_n(control['n_holding'])} of the {_n(control['n_entities'])} {label} values "
            f"tested individually -- mean {_pp(control['mean_gap_pp'])}, ranging "
            f"{_pp(control['min_gap_pp'])} to {_pp(control['max_gap_pp'])}.",
            f"So {label} concentrates it ({control['worst_entity']} is the worst) without "
            "being what produces it.",
        ]
    else:
        lines = [
            f"That may well be it. Held fixed, none of the {_n(control['n_entities'])} "
            f"{label} values still breaches target on its own -- mean "
            f"{_pp(control['mean_gap_pp'])}.",
            f"On this control the finding does not survive, and should be read as a "
            f"{label} effect.",
        ]

    if loo is not None:
        surviving = "still" if control.get("leave_one_out_survives") else "no longer"
        lines.append(
            f"Dropping the single worst {label} ({control['worst_entity']}) entirely leaves "
            f"the rest of the fleet {_pp(loo)} past target, which {surviving} breaches."
        )

    evidence = [
        _row("Control", label, "chat_facts.controls_detail[].control"),
        _row(f"{label.capitalize()} values tested", control["n_entities"],
             "chat_facts.controls_detail[].n_entities"),
        _row("Still past target", f"{_n(control['n_holding'])} of {_n(control['n_entities'])}",
             "chat_facts.controls_detail[].n_holding"),
        _row("Mean gap within", _pp(control["mean_gap_pp"]), "chat_facts.controls_detail[].mean_gap_pp"),
        _row("Range", f"{_pp(control['min_gap_pp'])} to {_pp(control['max_gap_pp'])}",
             "chat_facts.controls_detail[].min_gap_pp"),
    ]
    if loo is not None:
        evidence.append(
            _row(f"Excluding worst {label}", _pp(loo), f"controls[control={control['control']}].gap_pp")
        )

    return _answer(
        "CONTROL_CHALLENGE",
        " ".join(lines),
        evidence,
        ["Show me some of these trips", "Is the sample large enough?", "What do you recommend?"],
    )


# --- WHAT_IF_DATA_WRONG -------------------------------------------------------

def what_if_data_wrong(insight: dict[str, Any], slots: dict[str, Any]) -> dict[str, Any]:
    facts = _facts(insight)
    exclusions = facts.get("exclusions") or {}
    quality = insight.get("data_quality") or {}

    if not exclusions:
        return _answer(
            "WHAT_IF_DATA_WRONG",
            f"{_n(quality.get('excluded_pct'))}% of rows were excluded before this metric was "
            f"computed, and the insight carries {quality.get('confidence')} confidence because "
            "of it. I can't put a bound on what those rows would do to the number here -- the "
            "row counts behind that percentage could not be re-read.",
            [_row("Rows excluded", f"{_n(quality.get('excluded_pct'))}%", "data_quality.excluded_pct"),
             _row("Confidence", quality.get("confidence"), "data_quality.confidence")],
            ["Is the sample large enough?", "When did this begin?"],
        )

    flags = ", ".join(exclusions.get("excluded_flags") or []) or "no flags"
    lines = [
        f"{_n(exclusions['excluded_rows'])} rows -- {_n(exclusions['excluded_pct'])}% of the "
        f"{_n(exclusions['total_rows'])} in the window -- were excluded before this metric was "
        f"computed, flagged {flags}."
    ]

    if exclusions.get("bounds_derivable"):
        both = exclusions["best_case_breaches"] and exclusions["worst_case_breaches"]
        neither = not exclusions["best_case_breaches"] and not exclusions["worst_case_breaches"]
        lines.append(
            f"Put every one of them back and assume they all fall the favourable way and the "
            f"rate is {_n(exclusions['best_case_pct'])}%; assume they all fall the other way and "
            f"it is {_n(exclusions['worst_case_pct'])}%. Reported figure is "
            f"{_n(exclusions['reported_pct'])}%."
        )
        target = _target_pct(insight)
        if both:
            lines.append(
                f"Both ends of that range still breach the {_n(target)}% target, so the excluded "
                "rows cannot overturn the finding -- only move its size."
            )
        elif neither:
            lines.append(
                f"Neither end of that range breaches the {_n(target)}% target, so the finding "
                "does depend on the exclusion rule holding."
            )
        else:
            lines.append(
                f"One end of that range clears the {_n(target)}% target and the other does not, "
                "so the excluded rows are load-bearing for this finding. Treat it as a lead, not "
                "a conclusion, until they are understood."
            )
    else:
        lines.append(
            f"I can't bound it: {exclusions.get('bounds_note')}. What is on record is the share "
            "excluded and the confidence that produced."
        )

    lines.append(
        f"Data-quality confidence on this insight is {quality.get('confidence')}, which is "
        "assigned from that excluded share alone."
    )

    evidence = [
        _row("Rows excluded", exclusions["excluded_rows"], "chat_facts.exclusions.excluded_rows"),
        _row("Rows in window", exclusions["total_rows"], "chat_facts.exclusions.total_rows"),
        _row("Share excluded", f"{_n(exclusions['excluded_pct'])}%", "data_quality.excluded_pct"),
        _row("Flags excluded", flags, "chat_facts.exclusions.excluded_flags"),
        _row("Reported", f"{_n(exclusions['reported_pct'])}%", "metric.value"),
    ]
    if exclusions.get("bounds_derivable"):
        evidence.append(_row("Best case", f"{_n(exclusions['best_case_pct'])}%",
                             "chat_facts.exclusions.best_case_pct"))
        evidence.append(_row("Worst case", f"{_n(exclusions['worst_case_pct'])}%",
                             "chat_facts.exclusions.worst_case_pct"))
    evidence.append(_row("Confidence", quality.get("confidence"), "data_quality.confidence"))

    return _answer(
        "WHAT_IF_DATA_WRONG",
        " ".join(lines),
        evidence,
        ["Is the sample large enough?", "Show me some of these trips", "What do you recommend?"],
    )


# --- WHEN_DID_IT_START --------------------------------------------------------

def when_did_it_start(insight: dict[str, Any], slots: dict[str, Any]) -> dict[str, Any]:
    facts = _facts(insight)
    timeline = facts.get("timeline") or {}
    if not timeline:
        return _degraded("WHEN_DID_IT_START", facts, "dating the pattern")

    events = timeline.get("coincident_events") or []
    lines: list[str] = []

    if timeline.get("change_point"):
        lines.append(
            f"It steps at {timeline['change_point']}. The daily rate moves "
            f"{_pp(timeline['change_point_step_pp'])} across that date -- past the "
            f"{_n(timeline['change_point_threshold_pp'])}pp a change in this series has to clear "
            "before I will call it one."
        )
    else:
        lines.append(
            "No start date is inferable, and I would rather say that than pick a date."
        )
        lines.append(
            f"The series runs {timeline['first_day']} to {timeline['last_day']}, "
            f"{_n(timeline['days_with_data'])} days with data, and "
            f"{timeline.get('change_point_reason')}."
        )
        lines.append(
            f"Volume is steady through it -- {_n(timeline['volume_mean_per_day'])} rows a day on "
            f"average -- and the rate is past target on {_n(timeline['days_past_target'])} of "
            f"{_n(timeline['days_with_data'])} days. This does not look like an onset inside the "
            "window; it looks like the whole window."
        )

    if events:
        listed = "; ".join(f"{e.get('date')}: {e.get('note')}" for e in events)
        lines.append(f"Coincident events recorded against this insight: {listed}.")
    else:
        lines.append(
            "No coincident events are recorded against this insight, so there is nothing to line "
            "a start date up against even if one were visible."
        )

    evidence = [
        _row("Window", _metric(insight).get("window"), "metric.window"),
        _row("Days with data", timeline["days_with_data"], "chat_facts.timeline.days_with_data"),
        _row("Days past target", timeline["days_past_target"], "chat_facts.timeline.days_past_target"),
        _row("Mean rows per day", timeline["volume_mean_per_day"],
             "chat_facts.timeline.volume_mean_per_day"),
        _row("Largest before/after step", _pp(timeline.get("largest_step_pp")),
             "chat_facts.timeline.largest_step_pp"),
        _row("Step needed to call a change", f"{_n(timeline.get('change_point_threshold_pp'))}pp",
             "chat_facts.timeline.change_point_threshold_pp"),
        _row("Change point", timeline.get("change_point") or "none inferable",
             "chat_facts.timeline.change_point"),
        _row("Coincident events", len(events), "coincident_events"),
    ]

    return _answer(
        "WHEN_DID_IT_START",
        " ".join(lines),
        evidence,
        ["Show me some of these trips", "What if the excluded rows change this?", "What do you recommend?"],
    )


# --- SHOW_ME_EXAMPLES ---------------------------------------------------------

def show_me_examples(insight: dict[str, Any], slots: dict[str, Any]) -> dict[str, Any]:
    facts = _facts(insight)
    meta = facts.get("examples") or {}
    limit = slots.get("limit", intents.EXAMPLES_DEFAULT_LIMIT)

    if not facts.get("available") or not meta.get("available"):
        reason = meta.get("reason") or facts.get("reason") or "no row-level view is available"
        return _answer(
            "SHOW_ME_EXAMPLES",
            f"I can't show rows for this insight: {reason}. Row-level views are whitelisted per "
            "metric -- there is no free-form query behind this box, so where one has not been "
            "declared there is nothing to run.",
            [_row("Row-level view", "not available", "chat_facts.examples.available")],
            ["Why this dimension and not another?", "Is the sample large enough?"],
        )

    tenant_id = chat_facts.tenant_of(insight)
    try:
        rows, meta = chat_facts.fetch_examples(tenant_id, insight, limit)
    except Exception as exc:
        return _answer(
            "SHOW_ME_EXAMPLES",
            f"The row-level query for this insight did not run: {exc}.",
            [_row("Row-level view", "query failed", "chat_facts.examples")],
            ["Why this dimension and not another?", "Is the sample large enough?"],
        )

    filter_clause = ""
    if meta.get("slice_dim"):
        filter_clause = (
            f", filtered to the {meta['slice_dim_label']} this finding is attributed to "
            f"({meta['slice_value']})"
        )

    answer = (
        f"{_n(len(rows))} of the {_n(_adverse_rows(insight))} rows behind this finding"
        f"{filter_clause}, over {meta['window']}, with {' and '.join(meta['exclusions']) or 'no rows'} "
        f"excluded. The row test is the metric's own numerator, unchanged: {meta['predicate']}. "
        "This is one whitelisted query with the count bound as a parameter -- it is the only "
        "row-level view chat can run, and it cannot be widened from here."
    )

    evidence = [
        _row("Query", meta["query_id"], "chat_facts.examples.query_id"),
        _row("Table", meta["table"], "chat_facts.examples.table"),
        _row("Row test", meta["predicate"], "chat_facts.examples.predicate"),
        _row("Window", meta["window"], "metric.window"),
        _row("Rows returned", len(rows), "slots.limit"),
    ]
    if meta.get("slice_dim"):
        evidence.append(
            _row(f"Filtered {meta['slice_dim_label']}", meta["slice_value"], "attribution[].value")
        )

    table = {"columns": meta["columns"], "rows": rows}
    return _answer(
        "SHOW_ME_EXAMPLES",
        answer,
        evidence,
        ["Couldn't this just be the vendor?", "What do you recommend?", "When did this begin?"],
        table=table,
    )


# --- COMPARE_ENTITY -----------------------------------------------------------

def _find_entity(ranked: list[dict[str, Any]], needle: str) -> dict[str, Any] | None:
    wanted = needle.strip().lower()
    for entry in ranked:
        if entry["value"].lower() == wanted:
            return entry
    for entry in ranked:
        if wanted and (wanted in entry["value"].lower() or entry["value"].lower() in wanted):
            return entry
    return None


def compare_entity(insight: dict[str, Any], slots: dict[str, Any]) -> dict[str, Any]:
    facts = _facts(insight)
    ranked = facts.get("attribution_ranked") or []
    wanted = slots.get("entity_value")

    if not facts.get("available") or not ranked:
        return _degraded("COMPARE_ENTITY", facts, "comparing one entity to the others")

    if not wanted:
        named = ", ".join(entry["value"] for entry in ranked[:_MAX_ALTERNATIVES])
        return _answer(
            "COMPARE_ENTITY",
            f"Which one? The contributors ranked for this insight include {named}. Name one and "
            "I will place it against the rest.",
            [_row("Contributors ranked", len(ranked), "chat_facts.attribution_ranked")],
            ["Why this dimension and not another?", "Show me some of these trips"],
        )

    entry = _find_entity(ranked, wanted)
    if entry is None:
        named = "; ".join(
            f"{e['value']} ({e['dim_label']}, {_n(e['contribution_pct'])}%)"
            for e in ranked[:_MAX_ALTERNATIVES]
        )
        return _answer(
            "COMPARE_ENTITY",
            f"'{wanted}' was not among the contributors ranked for this insight, so I have no "
            f"figure for it here. I can only compare slices this metric was actually sliced by; "
            f"the strongest are {named}. If it is a slice that fell below the minimum sample, it "
            "was dropped before ranking rather than measured and cleared.",
            [_row("Requested", wanted, "slots.entity_value"),
             _row("Contributors ranked", len(ranked), "chat_facts.attribution_ranked")],
            ["Why this dimension and not another?", "Show me some of these trips"],
        )

    peers = [e for e in ranked if e["dim"] == entry["dim"]]
    worst = peers[0]
    target = _target_pct(insight)

    lines = [
        f"{entry['value']} carries {_n(entry['contribution_pct'])}% of the "
        f"{_n(_adverse_rows(insight))} adverse rows, across {_n(entry['n'])} rows of its own, "
        f"at {_n(entry['rate_pct'])}% against a {_n(target)}% target -- {_pp(entry['gap_pp'])}."
    ]
    if entry["rank_in_dim"] == 1:
        lines.append(
            f"That is the worst of the {_n(entry['slices_in_dim'])} {entry['dim_label']} values "
            f"ranked for this insight, and it ranks {_n(entry['rank'])} of "
            f"{_n(entry['slices_ranked'])} across every dimension we slice by."
        )
    else:
        lines.append(
            f"That places it {_n(entry['rank_in_dim'])} of the {_n(entry['slices_in_dim'])} "
            f"{entry['dim_label']} values ranked here, behind {worst['value']} at "
            f"{_n(worst['rate_pct'])}% ({_n(worst['contribution_pct'])}% of adverse rows)."
        )

    evidence = [
        _row("Entity", entry["value"], "chat_facts.attribution_ranked[].value"),
        _row("Dimension", entry["dim_label"], "chat_facts.attribution_ranked[].dim"),
        _row("Share of adverse rows", f"{_n(entry['contribution_pct'])}%", "attribution[].contribution_pct"),
        _row("Rows", entry["n"], "attribution[].n"),
        _row("Rate", f"{_n(entry['rate_pct'])}%", "chat_facts.attribution_ranked[].rate_pct"),
        _row("Gap past target", _pp(entry["gap_pp"]), "chat_facts.attribution_ranked[].gap_pp"),
        _row("Rank within dimension", f"{_n(entry['rank_in_dim'])} of {_n(entry['slices_in_dim'])}",
             "chat_facts.attribution_ranked[].rank_in_dim"),
    ]

    return _answer(
        "COMPARE_ENTITY",
        " ".join(lines),
        evidence,
        ["Show me some of these trips", "Couldn't this just be the vendor?", "What do you recommend?"],
    )


# --- WHAT_SHOULD_I_DO ---------------------------------------------------------

def what_should_i_do(insight: dict[str, Any], slots: dict[str, Any]) -> dict[str, Any]:
    facts = _facts(insight)
    recommended = (insight.get("narrative") or {}).get("recommended_actions") or []
    drafts = facts.get("action_drafts") or []

    if not recommended:
        return _answer(
            "WHAT_SHOULD_I_DO",
            "This insight carries no recommended action. That is a gap in the insight, not a "
            "judgement that nothing should be done -- the recommendation is written by the "
            "detector alongside the finding, and there is none on this one.",
            [_row("Recommended actions", 0, "narrative.recommended_actions")],
            ["Why this dimension and not another?", "Show me some of these trips"],
        )

    top = recommended[0]
    lines = [f"{top['title']}. {top['draft']}", f"Why that one: {top['rationale']}"]

    if len(recommended) > 1:
        others = "; ".join(action["title"] for action in recommended[1:])
        lines.append(f"Also on record for this insight: {others}.")

    if drafts:
        listed = "; ".join(f"{d['title']} ({d['status']})" for d in drafts)
        lines.append(f"Already drafted here: {listed}.")
    else:
        lines.append(
            "Nothing has been drafted for this insight yet. Drafting produces an email or ticket "
            "for a human to approve -- nothing is sent by approving it, and nothing is sent from "
            "this conversation at all."
        )

    evidence = [
        _row("Recommended action", top["title"], "narrative.recommended_actions[0].title"),
        _row("Rationale", top["rationale"], "narrative.recommended_actions[0].rationale"),
        _row("Drafts on this insight", len(drafts), "chat_facts.action_drafts"),
    ]

    return _answer(
        "WHAT_SHOULD_I_DO",
        " ".join(lines),
        evidence,
        ["Couldn't this just be the vendor?", "Show me some of these trips", "Is the sample large enough?"],
    )


# --- OUT_OF_SCOPE -------------------------------------------------------------

def out_of_scope(insight: dict[str, Any], slots: dict[str, Any]) -> dict[str, Any]:
    """The terminal intent. Fixed message, no evidence, no attempt at an answer."""
    return _answer(
        "OUT_OF_SCOPE",
        intents.refusal_message(),
        [],
        ["Couldn't this just be the vendor?", "Is the sample large enough?", "Show me some of these trips"],
    )


TEMPLATES: dict[str, Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]] = {
    "WHY_THIS_DIMENSION": why_this_dimension,
    "IS_SAMPLE_SUFFICIENT": is_sample_sufficient,
    "CONTROL_CHALLENGE": control_challenge,
    "WHAT_IF_DATA_WRONG": what_if_data_wrong,
    "WHEN_DID_IT_START": when_did_it_start,
    "SHOW_ME_EXAMPLES": show_me_examples,
    "COMPARE_ENTITY": compare_entity,
    "WHAT_SHOULD_I_DO": what_should_i_do,
    "OUT_OF_SCOPE": out_of_scope,
}

#: The only two intents whose prose a model may re-phrase. Both compare or
#: connect several fields, which is where a template reads most mechanically;
#: everything else is a single claim and gains nothing from being re-worded.
POLISHABLE = ("WHY_THIS_DIMENSION", "WHAT_SHOULD_I_DO")


def render(insight: dict[str, Any], intent_name: str, slots: dict[str, Any]) -> dict[str, Any]:
    """The answer for one classified turn. Never raises for a caller-supplied
    intent: an unknown label renders the refusal."""
    template = TEMPLATES.get(intent_name, out_of_scope)
    return template(insight, slots)


# --- optional re-phrasing -----------------------------------------------------

def polish(
    insight: dict[str, Any], answer: dict[str, Any], question: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Optionally re-phrase a template answer, and say what happened.

    Returns (answer, meta). The answer is the model's only when it came back
    parseable, non-empty, and with every number in it traceable to the packet
    -- otherwise the template's own prose is returned untouched. meta records
    which of those it was, so the endpoint can log a phrasing that was thrown
    away rather than silently swallow it.
    """
    meta = {"polished": False, "reason": "not eligible", "tokens_in": 0, "tokens_out": 0}
    if answer["intent"] not in POLISHABLE:
        return answer, meta
    if not get_settings().llm_enabled:
        meta["reason"] = "pulse.llm.enabled is false"
        return answer, meta

    payload = {
        "question": question,
        "intent": answer["intent"],
        "template_answer": answer["answer"],
        "evidence": answer["evidence"],
    }
    prompt = _PROMPT_PATH.read_text() + "\n\n## Input\n\n" + json.dumps(payload, indent=2, default=str)
    meta["tokens_in"] = len(prompt) // 4

    try:
        raw = llm_client.complete(
            system="Respond with strict JSON only, no markdown fences.",
            prompt=prompt,
            max_tokens=800,
            # 'narrate': this call writes no figure, it re-words an answer the
            # template already wrote. app/llm/ledger.py bills it as prose.
            call_type="narrate",
        )
    except Exception as exc:
        meta["reason"] = f"model call failed: {exc}"
        return answer, meta

    meta["tokens_out"] = len(raw) // 4
    parsed = parse_json_object(raw)
    text = str((parsed or {}).get("answer", "")).strip()
    if not text:
        meta["reason"] = "model returned no answer field"
        return answer, meta

    result = validator.validate_text(insight, text)
    if not result.ok:
        meta["reason"] = f"ungrounded numbers: {sorted(result.ungrounded)}"
        return answer, meta

    meta.update({"polished": True, "reason": "validated against the packet"})
    return {**answer, "answer": text}, meta
