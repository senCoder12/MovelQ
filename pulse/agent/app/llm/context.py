"""Who a model call is being made for.

``tenant_id`` is required on every ledger row, and ``scan_run_id`` is what ties a
row to the run that caused it. Neither is a natural argument to ``complete()``:
the tenant is a property of the request the agent is serving, not of the prompt,
and threading it through every intermediate function is exactly the kind of
convention that one call site eventually forgets.

So they live in context variables, set once per request by the middleware in
app/main.py from ``X-Tenant-Id`` and ``X-Scan-Run-Id``, and read by
app/llm/ledger.py. Context variables rather than globals because FastAPI runs
handlers on a shared thread pool -- a module-level global would leak one
request's tenant into the next one's ledger rows.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Iterator

_tenant_id: ContextVar[str | None] = ContextVar("pulse_tenant_id", default=None)
_scan_run_id: ContextVar[str | None] = ContextVar("pulse_scan_run_id", default=None)
_insight_id: ContextVar[str | None] = ContextVar("pulse_insight_id", default=None)


@dataclass(frozen=True)
class CallContext:
    tenant_id: str | None
    scan_run_id: str | None
    insight_id: str | None


def current() -> CallContext:
    return CallContext(_tenant_id.get(), _scan_run_id.get(), _insight_id.get())


def tenant_id() -> str | None:
    return _tenant_id.get()


def scan_run_id() -> str | None:
    return _scan_run_id.get()


@contextmanager
def bind(
    tenant_id: str | None = None,
    scan_run_id: str | None = None,
    insight_id: str | None = None,
) -> Iterator[None]:
    """Set what is given, leave the rest as it was, restore on exit.

    A None argument means "unchanged", not "clear" -- app/api/actions.py binds
    only ``insight_id`` and must not blank out the tenant the middleware set.
    """
    tokens = []
    if tenant_id is not None:
        tokens.append((_tenant_id, _tenant_id.set(tenant_id)))
    if scan_run_id is not None:
        tokens.append((_scan_run_id, _scan_run_id.set(scan_run_id)))
    if insight_id is not None:
        tokens.append((_insight_id, _insight_id.set(insight_id)))
    try:
        yield
    finally:
        for variable, token in reversed(tokens):
            variable.reset(token)
