"""Layer 2 -- every model call is metered, and no call site can opt out.

The claim under test: there is exactly one way to reach a model from this
process, it is wrapped, and the wrapper writes a token_usage row whether the
call succeeds or fails.

Three kinds of assertion, because one alone would be weak:

* **Static** -- the four modules the architecture allows to reach a model
  (api/leadership, api/actions, actions/drafters, main) are walked at the AST
  level. Anything that touches the provider SDK directly, or calls the private
  ``_complete``, or calls ``complete`` without declaring a ``call_type``, fails
  here rather than in production three weeks later.
* **Behavioural** -- a stubbed provider proves what actually lands in a row:
  the token counts, the measured duration, the model, the tenant and scan id
  from context.
* **Failure** -- a provider that raises still writes a row (tokens 0, error
  set) and still propagates, and a ledger that is itself broken does not cost
  the caller their answer.

The complementary assertion lives in tests/test_degraded_mode.py: with the model
switched off, a full scan writes *zero* rows. Together they are the claim --
this file proves the ledger counts everything, that one proves the count is
zero when it should be.
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path
from typing import Any

import pytest

from app.llm import client as llm_client
from app.llm import context, ledger

APP_ROOT = Path(__file__).resolve().parents[1] / "app"

#: The four modules tests/test_no_llm_imports.py permits to reach the model
#: layer. Every one of them is checked here for a bypass.
MODEL_REACHING_MODULES = (
    "app/api/leadership.py",
    "app/api/actions.py",
    "app/actions/drafters.py",
    "app/main.py",
)

#: Names that would mean a model call that skipped the wrapper.
_BYPASS_NAMES = {"_complete", "generate_content", "generate_content_stream"}
_PROVIDER_MODULES = ("google.genai", "google.generativeai", "anthropic", "openai")


def _tree(relative_path: str) -> ast.Module:
    path = APP_ROOT.parent / relative_path
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _called_name(node: ast.Call) -> str:
    """The trailing attribute or bare name of a call target."""
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return ""


# --------------------------------------------------------------------------
# Static: no bypass path exists
# --------------------------------------------------------------------------


def test_complete_is_the_metered_wrapper() -> None:
    """``client.complete`` is what the decorator produced, not the raw call."""
    assert getattr(llm_client.complete, "__ledger_metered__", False) is True, (
        "app.llm.client.complete is not wrapped by app.llm.client.metered; "
        "nothing would record the call"
    )
    assert llm_client.complete is not llm_client._complete


@pytest.mark.parametrize("module_path", MODEL_REACHING_MODULES)
def test_no_module_reaches_the_provider_directly(module_path: str) -> None:
    """None of the four imports a model SDK. Only app/llm/client.py may."""
    imported: list[str] = []
    for node in ast.walk(_tree(module_path)):
        if isinstance(node, ast.Import):
            imported += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
            imported += [f"{node.module}.{alias.name}" for alias in node.names]
    offenders = [
        name for name in imported
        if any(name == p or name.startswith(p + ".") or p.startswith(name + ".") for p in _PROVIDER_MODULES)
    ]
    assert not offenders, (
        f"{module_path} imports a model SDK directly ({offenders}); a call made through it "
        "would never reach the ledger"
    )


@pytest.mark.parametrize("module_path", MODEL_REACHING_MODULES)
def test_no_module_calls_the_unmetered_entry_point(module_path: str) -> None:
    """Nothing calls ``_complete`` or the SDK's own generate methods."""
    offenders = sorted({
        _called_name(node) for node in ast.walk(_tree(module_path))
        if isinstance(node, ast.Call) and _called_name(node) in _BYPASS_NAMES
    })
    assert not offenders, (
        f"{module_path} calls {offenders} -- that path skips app.llm.client.metered "
        "and writes no token_usage row"
    )


@pytest.mark.parametrize("module_path", MODEL_REACHING_MODULES)
def test_every_complete_call_declares_a_call_type(module_path: str) -> None:
    """A ledger where every row says "other" groups by nothing.

    ``call_type`` is keyword-only and has no default, so this is also enforced
    at runtime -- but a TypeError raised during a demo is a worse place to find
    out than here.
    """
    for node in ast.walk(_tree(module_path)):
        if not isinstance(node, ast.Call) or _called_name(node) != "complete":
            continue
        keywords = {keyword.arg for keyword in node.keywords}
        assert "call_type" in keywords, (
            f"{module_path}:{node.lineno} calls complete() without call_type"
        )
        call_type = next(k.value for k in node.keywords if k.arg == "call_type")
        assert isinstance(call_type, ast.Constant) and call_type.value in ledger.CALL_TYPES, (
            f"{module_path}:{node.lineno} passes a call_type that is not one of "
            f"{ledger.CALL_TYPES}; the ck_token_usage_call_type constraint would reject the row"
        )


def test_every_model_reaching_module_routes_through_the_wrapper() -> None:
    """The positive half: each module that reaches a model does so via
    ``client.complete``. A module in the allowed list that has quietly stopped
    calling it has either lost its model call or found another way to make one.

    app/main.py is exempt -- it wires routers together and makes no call itself.
    """
    for module_path in MODEL_REACHING_MODULES:
        source = (APP_ROOT.parent / module_path).read_text(encoding="utf-8")
        if module_path == "app/main.py":
            assert "llm_client" not in source, "app/main.py should not call a model itself"
            continue
        if "llm_client" not in source:
            continue  # api/actions.py delegates to drafters; it holds no call site
        assert "llm_client.complete(" in source, (
            f"{module_path} imports the client but calls something other than complete()"
        )


# --------------------------------------------------------------------------
# Behavioural: what actually lands in a row
# --------------------------------------------------------------------------


@pytest.fixture
def captured(monkeypatch: pytest.MonkeyPatch) -> list[ledger.Usage]:
    """Intercept ledger.record so the assertions do not need a database.

    Patched on the module the client imported, which is the same object -- the
    real ``record`` is exercised separately in test_record_never_raises.
    """
    rows: list[ledger.Usage] = []
    monkeypatch.setattr(ledger, "record", rows.append)
    return rows


def _stub_completion(**overrides: Any) -> llm_client.Completion:
    defaults = dict(text="hello", model="gemini-2.5-pro", tokens_in=120, tokens_out=45, cached_tokens=16)
    return llm_client.Completion(**{**defaults, **overrides})


def test_a_successful_call_records_tokens_model_and_duration(
    monkeypatch: pytest.MonkeyPatch, captured: list[ledger.Usage]
) -> None:
    monkeypatch.setattr(llm_client, "_complete", lambda *a, **k: _stub_completion())
    metered = llm_client.metered(llm_client._complete)

    with context.bind(tenant_id="catalyst", scan_run_id="11111111-1111-1111-1111-111111111111"):
        text = metered(system="s", prompt="p", call_type="draft_action")

    assert text == "hello"
    assert len(captured) == 1
    usage = captured[0]
    assert (usage.call_type, usage.model) == ("draft_action", "gemini-2.5-pro")
    assert (usage.tokens_in, usage.tokens_out, usage.cached_tokens) == (120, 45, 16)
    assert usage.error is None and usage.cache_hit is False
    assert usage.duration_ms >= 0


def test_context_supplies_tenant_and_scan_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """The row is attributed from context, not from an argument every call site
    would have to remember to pass."""
    rows: list[tuple] = []
    monkeypatch.setattr(ledger.platform_db, "execute", lambda sql, params: rows.append(params))
    with context.bind(tenant_id="vanta", scan_run_id="22222222-2222-2222-2222-222222222222",
                      insight_id="ota"):
        ledger.record(ledger.Usage(call_type="narrate", model="gemini-2.5-flash"))
        ledger.flush()

    assert rows, "no row was written"
    tenant_id, scan_run_id, insight_id, call_type = rows[0][:4]
    assert tenant_id == "vanta"
    assert scan_run_id == "22222222-2222-2222-2222-222222222222"
    assert insight_id == "ota"
    assert call_type == "narrate"


def test_a_cache_hit_is_recorded_with_no_tokens(monkeypatch: pytest.MonkeyPatch,
                                                captured: list[ledger.Usage]) -> None:
    """Our cache, not the provider's. A hit spends nothing but is still a call
    the endpoint served -- without a row the cache hit rate would read 0%."""
    ledger.record_cache_hit("leadership_narrative", "gemini-2.5-pro")
    assert len(captured) == 1
    assert captured[0].cache_hit is True
    assert (captured[0].tokens_in, captured[0].tokens_out) == (0, 0)


def test_a_call_with_no_tenant_is_refused_before_it_dials_out(
    monkeypatch: pytest.MonkeyPatch, captured: list[ledger.Usage]
) -> None:
    """An unattributable row is worse than a loud error, so the wrapper refuses
    the call rather than making it and recording it against no one."""
    called = []
    metered = llm_client.metered(lambda *a, **k: called.append(1) or _stub_completion())

    with pytest.raises(ValueError, match="no tenant in context"):
        metered(system="s", prompt="p", call_type="other")

    assert not called, "the provider was reached despite there being no tenant to bill"
    assert not captured


# --------------------------------------------------------------------------
# Failure: a failed call has a latency cost even with no tokens
# --------------------------------------------------------------------------


def test_a_failed_call_still_writes_a_row(captured: list[ledger.Usage]) -> None:
    def boom(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("rate limited")

    metered = llm_client.metered(boom)
    with context.bind(tenant_id="catalyst"):
        with pytest.raises(RuntimeError, match="rate limited"):
            metered(system="s", prompt="p", call_type="leadership_narrative")

    assert len(captured) == 1, "a provider failure wrote no ledger row"
    usage = captured[0]
    assert (usage.tokens_in, usage.tokens_out) == (0, 0)
    assert usage.error == "RuntimeError: rate limited"
    assert usage.call_type == "leadership_narrative"


def test_record_never_raises_when_the_ledger_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    """A ledger failure must never fail a model call -- catch, log, move on."""
    def unavailable(*args: Any, **kwargs: Any) -> None:
        raise ConnectionError("Neon is asleep")

    monkeypatch.setattr(ledger.platform_db, "execute", unavailable)
    with context.bind(tenant_id="catalyst"):
        ledger.record(ledger.Usage(call_type="other", model="gemini-2.5-pro"))
        ledger.flush()  # the write already failed on the worker thread; nothing propagates


def test_a_broken_ledger_does_not_break_the_call(monkeypatch: pytest.MonkeyPatch) -> None:
    """The end-to-end version of the rule above: the caller still gets an answer."""
    monkeypatch.setattr(ledger.platform_db, "execute",
                        lambda *a, **k: (_ for _ in ()).throw(ConnectionError("down")))
    monkeypatch.setattr(llm_client, "_complete", lambda *a, **k: _stub_completion(text="still fine"))
    metered = llm_client.metered(llm_client._complete)

    with context.bind(tenant_id="catalyst"):
        assert metered(system="s", prompt="p", call_type="other") == "still fine"


def test_an_unknown_call_type_is_normalised_rather_than_dropped(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    """ck_token_usage_call_type would reject the row outright, and a rejected
    write is a silently missing row. Recorded as 'other' instead, with a log line."""
    rows: list[tuple] = []
    monkeypatch.setattr(ledger.platform_db, "execute", lambda sql, params: rows.append(params))
    with context.bind(tenant_id="catalyst"):
        ledger.record(ledger.Usage(call_type="summarise_everything", model="m"))
        ledger.flush()
    assert rows and rows[0][3] == "other"


# --------------------------------------------------------------------------
# The middleware that binds context in the first place
# --------------------------------------------------------------------------


def test_the_middleware_binds_tenant_and_scan_run_for_every_request() -> None:
    """Binding happens once, in app/main.py, for every request -- not per
    handler, where a handler added later could forget."""
    source = (APP_ROOT / "main.py").read_text(encoding="utf-8")
    assert '@app.middleware("http")' in source
    assert "X-Tenant-Id" in source and "X-Scan-Run-Id" in source


def test_context_does_not_leak_between_binds() -> None:
    """FastAPI runs handlers on a shared pool; a tenant that outlived its
    request would end up on the next request's ledger rows."""
    assert context.tenant_id() is None
    with context.bind(tenant_id="catalyst"):
        with context.bind(insight_id="ota"):
            # A None argument means "unchanged", not "clear".
            assert context.current().tenant_id == "catalyst"
            assert context.current().insight_id == "ota"
        assert context.current().insight_id is None
    assert context.tenant_id() is None


def test_the_agent_can_reach_postgres_configuration() -> None:
    """The ledger needs a platform database, and it reads the same variables the
    backend does. This asserts the wiring, not a live connection."""
    platform_db = importlib.import_module("app.platform_db")
    assert hasattr(platform_db, "dsn") and hasattr(platform_db, "pool")
    jdbc = platform_db._dsn_from_jdbc(
        "jdbc:postgresql://host.example/neondb?sslmode=require", "user", "p@ss")
    assert jdbc == "postgresql://user:p%40ss@host.example/neondb?sslmode=require"
