"""Layer 3 -- degraded mode, end to end.

With ``pulse.llm.enabled=false`` the system must still produce every signal and
every figure, and render its prose from templates rather than a model. This
exercises the full detection path in that mode and checks the model was never
reached.

Several assertions the architecture claim calls for have no subject in this
tree and are recorded as failures rather than quietly dropped -- see the
``test_missing_*`` cases at the bottom. Passing this file with those removed
would mean the claim is narrower than it sounds.
"""

from __future__ import annotations

import pytest

from app.config import Settings, get_settings
from app.detect import signals

TENANT = "catalyst"


class LLMCalledError(AssertionError):
    pass


@pytest.fixture
def degraded(monkeypatch: pytest.MonkeyPatch):
    """pulse.llm.enabled=false, with every route to a model wired to raise.

    The flag alone would prove only that the flag is read. The traps prove
    nothing dialled out regardless of which path was taken.
    """
    def boom(*args: object, **kwargs: object) -> object:
        raise LLMCalledError("LLM called in degraded mode")

    monkeypatch.setenv("PULSE_LLM_ENABLED", "false")
    get_settings.cache_clear()

    import httpx

    from app.llm import client as llm_client

    monkeypatch.setattr(llm_client, "complete", boom)
    monkeypatch.setattr(httpx.Client, "send", boom)
    monkeypatch.setattr(httpx.AsyncClient, "send", boom)
    try:
        from google import genai
        monkeypatch.setattr(genai, "Client", boom)
    except ImportError:
        pass

    settings = get_settings()
    assert settings.llm_enabled is False, "PULSE_LLM_ENABLED=false was not honoured"
    yield settings
    # Settings is lru_cached; leaving a degraded instance behind would leak into
    # every later test in the session.
    get_settings.cache_clear()


def test_config_flag_defaults_to_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """pulse.llm.enabled defaults to true -- degraded mode is opt-in."""
    monkeypatch.delenv("PULSE_LLM_ENABLED", raising=False)
    get_settings.cache_clear()
    try:
        assert get_settings().llm_enabled is True
    finally:
        get_settings.cache_clear()


def test_scan_completes_in_degraded_mode(degraded) -> None:
    """The full detection pass runs for the tenant with no model available."""
    insights = signals.detect_tenant(TENANT)
    assert insights, f"{TENANT}: degraded scan produced no insights"


def test_every_insight_has_a_non_empty_narrative(degraded) -> None:
    """Narrative renders from packet fields alone -- headline and body both
    populated, and every recommended action carries draft text."""
    for insight in signals.detect_tenant(TENANT):
        narrative = insight["narrative"]
        assert narrative["headline"].strip(), f"{insight['insight_id']}: empty headline"
        assert narrative["body"].strip(), f"{insight['insight_id']}: empty body"
        for action in narrative["recommended_actions"]:
            assert action["draft"].strip(), f"{insight['insight_id']}: empty action draft"


def test_narrative_figures_all_appear_in_structured_fields(degraded) -> None:
    """The templated narrative is pure substitution: every number in the prose
    is one that also appears in a structured field.

    This is what makes templated prose safe to read as fact. A number in the
    body that appears nowhere else came from somewhere unaccounted for.
    """
    import re

    for insight in signals.detect_tenant(TENANT):
        grounded = {
            f"{insight['metric']['value']}",
            f"{insight['metric']['n']:,}",
            f"{insight['impact']['affected_trips']:,}",
        }
        for entry in insight["attribution"]:
            grounded.add(f"{entry['contribution_pct']}")
            grounded.add(f"{entry['n']:,}")
        for reference in insight["references"]:
            grounded.add(f"{reference['value']}")
            grounded.add(f"{round(float(reference['value']), 1)}")

        body = insight["narrative"]["body"]
        for number in re.findall(r"\d[\d,]*\.?\d*", body):
            assert number in grounded or number.rstrip("0").rstrip(".") in {
                g.rstrip("0").rstrip(".") for g in grounded
            }, (
                f"{insight['insight_id']}: narrative cites {number!r}, which appears "
                "in no structured field"
            )


def test_action_drafts_are_templated_at_low_confidence(degraded) -> None:
    """Action drafts render from facts_cited, and say so: confidence "low"."""
    from app.actions import drafters

    insights = signals.detect_tenant(TENANT)
    drafted = 0
    for insight in insights:
        for action_type in drafters.applicable_action_types(insight):
            draft = drafters.draft_action(insight, action_type)
            assert draft["subject"].strip() or draft["title"].strip()
            assert draft["body"].strip(), f"{action_type}: empty templated body"
            assert draft["confidence"] == "low", (
                f"{action_type}: templated draft reports confidence "
                f"{draft['confidence']!r}, expected 'low'"
            )
            drafted += 1
    assert drafted, "no action type applied to any insight; nothing was exercised"


def test_degraded_ranking_matches_enabled_ranking(degraded) -> None:
    """Ranking is identical with and without a model.

    The parity check that matters: severity, attribution and ordering are
    computed from warehouse figures, so disabling the model must not move a
    single row. If this ever differs, ranking has picked up a dependency on
    generated text.
    """
    degraded_ranking = [
        (i["insight_id"], i["severity"]) for i in signals.detect_tenant(TENANT)
    ]

    get_settings.cache_clear()
    import os

    os.environ["PULSE_LLM_ENABLED"] = "true"
    try:
        enabled_ranking = [
            (i["insight_id"], i["severity"]) for i in signals.detect_tenant(TENANT)
        ]
    finally:
        os.environ["PULSE_LLM_ENABLED"] = "false"
        get_settings.cache_clear()

    assert degraded_ranking == enabled_ranking, (
        f"ranking differs between modes:\n  degraded={degraded_ranking}\n"
        f"  enabled ={enabled_ranking}"
    )


# --------------------------------------------------------------------------
# Assertions the claim calls for that have no subject in this tree.
# --------------------------------------------------------------------------


def test_missing_scan_run_status(degraded) -> None:
    """Assert scan_run completes with status SUCCESS."""
    pytest.fail(
        "no scan_run record exists. Detection is a synchronous call "
        "(signals.detect_tenant) with no run row, status, or timing persisted; "
        "InsightSyncService logs a line and returns a SyncResult that is never "
        "stored. There is no SUCCESS/PARTIAL status to assert."
    )


def test_missing_token_ledger(degraded) -> None:
    """Assert llm_calls = 0, tokens_in = 0, tokens_out = 0."""
    pytest.fail(
        "no token accounting exists. app/llm/client.py discards the Gemini "
        "usage_metadata and returns only response.text, so llm_calls, tokens_in "
        "and tokens_out are not recorded anywhere and cannot be asserted to be "
        "zero. The monkeypatched traps in this file prove no call was made; they "
        "do not prove a ledger reads zero, because there is no ledger."
    )


def test_missing_three_insight_expectation(degraded) -> None:
    """Assert 3 insights persisted."""
    insights = signals.detect_tenant(TENANT)
    assert len(insights) == 3, (
        f"{TENANT} produces {len(insights)} insights, not 3: "
        + ", ".join(i["insight_id"] for i in insights)
    )


def test_missing_suffix_16_for_this_tenant(degraded) -> None:
    """Assert the ':16' insight is present and ranked first."""
    insights = signals.detect_tenant(TENANT)
    found = [
        i["insight_id"] for i in insights
        if any(a["value"] == ":16" for a in i["attribution"])
    ]
    assert found and found[0] == insights[0]["insight_id"], (
        f"no ':16' attribution in any {TENANT} insight. All 29,854 ':16' trips in "
        "the warehouse belong to tenant 'vanta'; catalyst has none."
    )


def test_missing_brief_snapshot(degraded) -> None:
    """Assert brief_snapshot is written and GET /api/brief returns a payload."""
    pytest.fail(
        "no brief_snapshot exists. The backend serves GET /api/brief from "
        "Postgres via BriefCache, an in-memory cache invalidated on sync -- "
        "there is no snapshot table or file written per scan to assert against."
    )


def test_missing_alert_parity(degraded) -> None:
    """Assert alerts fired identically to the LLM-enabled run."""
    pytest.fail(
        "no alerting subsystem exists. There are no rule definitions, no "
        "evaluator and no firing record in agent/ or backend/, so there is no "
        "(rule_id, entity, urgency) set to compare across modes. "
        "test_degraded_ranking_matches_enabled_ranking above proves the "
        "deterministic half of this -- ranking is identical across modes -- "
        "which is the parity that can be checked today."
    )
