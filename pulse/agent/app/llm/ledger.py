"""The token ledger -- one row in Postgres per model call.

Every call the agent makes to a model writes a row here, including the ones that
fail. That turns "we made no LLM calls" from an absence into a measurement: a
degraded-mode scan is proved LLM-free by ``SELECT COUNT(*) ... WHERE
scan_run_id = ?`` returning 0, not only by a monkeypatched trap that nothing
tripped.

Two rules govern everything in this module:

1. **Fire and forget relative to the response.** The write happens on a
   background thread; ``record`` returns immediately. The model's answer does
   not wait on a round trip to us-east-2.
2. **A ledger failure never fails a model call.** Every path here catches
   broadly and logs. An unreachable platform database costs us the row, and
   the run that noticed records ``ledger_unavailable`` in its degraded reasons
   -- it does not cost the caller their answer.

The one thing that *is* enforced strictly is the tenant: a call with no tenant
in context is refused before it dials out (see app/llm/client.py). That is not a
ledger failure, it is a programming error, and it is the same rule app/db.py
applies to every warehouse read.
"""

from __future__ import annotations

import atexit
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from app import platform_db
from app.llm import context

log = logging.getLogger(__name__)

CALL_TYPES = ("narrate", "draft_action", "leadership_narrative", "route_intent", "other")

#: Matches ck_token_usage_call_type in V7__token_usage.sql. A call_type outside
#: this set would be rejected by the check constraint, and a rejected ledger
#: write is a silently missing row -- so it is normalised to 'other' here, where
#: the substitution can at least be logged.
_DEFAULT_CALL_TYPE = "other"

#: Postgres TEXT has no limit, but an SDK stack trace in a ledger row is noise.
_MAX_ERROR_CHARS = 500

_INSERT = """
INSERT INTO token_usage (
    tenant_id, scan_run_id, insight_id, call_type, model,
    tokens_in, tokens_out, cached_tokens, duration_ms, cache_hit, error
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""

#: One thread. Ledger writes are small, ordered-enough, and never urgent; the
#: cost of getting this wrong is a thread per model call.
_writer = ThreadPoolExecutor(max_workers=1, thread_name_prefix="token-ledger")
atexit.register(lambda: _writer.shutdown(wait=True))


@dataclass(frozen=True)
class Usage:
    """One model call, as the ledger records it."""

    call_type: str
    model: str
    tokens_in: int = 0
    tokens_out: int = 0
    cached_tokens: int = 0
    duration_ms: int = 0
    cache_hit: bool = False
    error: str | None = None
    tenant_id: str | None = None
    scan_run_id: str | None = None
    insight_id: str | None = None


def record(usage: Usage) -> None:
    """Queue one row. Returns immediately; never raises."""
    try:
        row = _row(usage)
    except Exception as exc:
        log.warning("token ledger: could not build row: %s", exc)
        return
    try:
        _writer.submit(_write, row)
    except Exception as exc:
        # Interpreter shutdown, or a saturated queue. Losing the row is the
        # correct outcome; losing the caller's answer is not.
        log.warning("token ledger: could not queue write: %s", exc)


def record_cache_hit(call_type: str, model: str, duration_ms: int = 0) -> None:
    """A response served from the agent's own cache: no request left the
    process, so no tokens and no provider latency, but the call still happened
    and the cache hit rate is computed from these rows."""
    record(Usage(call_type=call_type, model=model, duration_ms=duration_ms, cache_hit=True))


def _row(usage: Usage) -> tuple:
    ctx = context.current()
    tenant_id = usage.tenant_id or ctx.tenant_id
    if not tenant_id:
        raise ValueError("token ledger row has no tenant_id")

    call_type = usage.call_type
    if call_type not in CALL_TYPES:
        log.warning("token ledger: unknown call_type %r, recording as %r", call_type, _DEFAULT_CALL_TYPE)
        call_type = _DEFAULT_CALL_TYPE

    error = usage.error
    if error is not None and len(error) > _MAX_ERROR_CHARS:
        error = error[:_MAX_ERROR_CHARS]

    return (
        tenant_id,
        usage.scan_run_id or ctx.scan_run_id,
        usage.insight_id or ctx.insight_id,
        call_type,
        usage.model,
        max(0, int(usage.tokens_in)),
        max(0, int(usage.tokens_out)),
        max(0, int(usage.cached_tokens)),
        max(0, int(usage.duration_ms)),
        bool(usage.cache_hit),
        error,
    )


def _write(row: tuple) -> None:
    try:
        platform_db.execute(_INSERT, row)
    except Exception as exc:
        # Unreachable database, missing migration, closed pool. One line, no retry:
        # a retry loop on a background writer is how a transient outage becomes a
        # permanent one.
        log.warning("token ledger write dropped: %s", exc)


def flush(timeout: float = 5.0) -> None:
    """Block until queued writes have been attempted.

    Only for callers that need the ledger to be readable straight afterwards --
    tests, and the end of a scan, which reads its own rows back. Never called on
    a request path.
    """
    try:
        _writer.submit(lambda: None).result(timeout=timeout)
    except Exception as exc:
        log.warning("token ledger flush did not complete: %s", exc)
