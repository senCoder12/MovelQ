"""Postgres access for the agent.

The agent owns DuckDB (app/db.py) and, until now, held no Postgres credentials at
all -- the backend was the only thing that talked to the platform database. The
token ledger changes that, and deliberately: a ledger write sits on the latency
path of every model call, and routing it through Java would put a round trip to
us-east-2 in front of a round trip to Gemini on every single call.

So the agent gets its own connection, reading the same three environment
variables the backend does. ``PULSE_DB_URL`` is a JDBC URL because that is the
form the backend needs; ``_dsn_from_jdbc`` converts it. ``NEON_DATABASE_URL``
(the ``postgres://`` URI Neon hands out) is accepted directly, which is what
backend/.env actually holds.

Everything here is best-effort by construction. ``pool()`` returns None rather
than raising when no credentials are configured or the pool cannot be opened,
and the one write path (app/llm/ledger.py) treats None as "no ledger today".
The agent must keep working with the platform database unreachable -- that is
the same posture the backend takes towards the agent.
"""

from __future__ import annotations

import atexit
import logging
import os
import threading
from typing import Any, Iterator
from contextlib import contextmanager
from urllib.parse import quote, urlsplit, urlunsplit

# Imported for its side effect: app.config loads agent/.env and backend/.env into
# the process environment at import time, and the variables read below come from
# there. Reading os.environ without it works only when something else happened to
# import app.config first.
from app import config as _config  # noqa: F401

log = logging.getLogger(__name__)

#: Small on purpose. The agent's Postgres traffic is ledger writes and the cost
#: query -- a handful of statements per scan, not a request-serving workload.
#: Neon's pooler is shared, and idle connections there are not free.
_MIN_POOL_SIZE = 1
_MAX_POOL_SIZE = 3

_lock = threading.Lock()
_pool: Any | None = None
_pool_attempted = False


def _dsn_from_jdbc(jdbc_url: str, user: str | None, password: str | None) -> str:
    """``jdbc:postgresql://host/db?sslmode=require`` -> a libpq-style URI.

    The backend keeps credentials out of its URL on purpose (they turn up in
    connection errors and Flyway output), so they arrive separately and are
    spliced back in here.
    """
    stripped = jdbc_url[len("jdbc:"):] if jdbc_url.startswith("jdbc:") else jdbc_url
    parts = urlsplit(stripped)
    netloc = parts.netloc
    if user:
        credentials = quote(user, safe="")
        if password:
            credentials += ":" + quote(password, safe="")
        netloc = f"{credentials}@{netloc}"
    return urlunsplit(("postgresql", netloc, parts.path, parts.query, ""))


def dsn() -> str | None:
    """The connection string, or None when nothing is configured.

    Precedence matches the backend's: an explicit ``PULSE_DB_URL`` wins over
    anything derived from ``NEON_DATABASE_URL``.
    """
    url = os.getenv("PULSE_DB_URL")
    if url:
        return _dsn_from_jdbc(url, os.getenv("PULSE_DB_USER"), os.getenv("PULSE_DB_PASSWORD"))

    neon = os.getenv("NEON_DATABASE_URL")
    if neon and not neon.startswith("jdbc:"):
        # channel_binding is dropped for the same reason the backend drops it:
        # not every client accepts it, and it buys nothing over sslmode=require.
        parts = urlsplit(neon.strip())
        query = "&".join(
            pair for pair in parts.query.split("&")
            if pair and not pair.startswith("channel_binding=")
        )
        return urlunsplit(("postgresql", parts.netloc, parts.path, query, ""))
    return None


def pool() -> Any | None:
    """The shared connection pool, opened on first use. None if unavailable.

    Opening is attempted exactly once per process: a missing psycopg install or
    an unreachable database should cost one failed attempt and a log line, not a
    retry storm on the path of every model call.
    """
    global _pool, _pool_attempted
    if _pool is not None or _pool_attempted:
        return _pool
    with _lock:
        if _pool is not None or _pool_attempted:
            return _pool
        _pool_attempted = True
        connection_string = dsn()
        if not connection_string:
            log.warning(
                "no Postgres credentials configured (PULSE_DB_URL / NEON_DATABASE_URL); "
                "token ledger writes will be dropped"
            )
            return None
        try:
            from psycopg_pool import ConnectionPool

            _pool = ConnectionPool(
                connection_string,
                min_size=_MIN_POOL_SIZE,
                max_size=_MAX_POOL_SIZE,
                # Do not block startup on Neon waking up from scale-to-zero.
                open=True,
                timeout=10.0,
                kwargs={"application_name": "pulse-agent"},
            )
        except Exception as exc:  # ImportError, bad DSN, unreachable host
            log.warning("Postgres pool unavailable: %s", exc)
            _pool = None
        else:
            # Close the pool before the interpreter tears the thread machinery
            # down. Without this, psycopg_pool's finalizer tries to join its
            # worker threads during shutdown and raises PythonFinalizationError
            # -- harmless, but it prints a traceback after every CLI run.
            atexit.register(reset)
        return _pool


@contextmanager
def connection() -> Iterator[Any]:
    """A pooled connection. Raises if no pool is available -- callers that must
    not fail (the ledger) check ``pool()`` first or catch."""
    connection_pool = pool()
    if connection_pool is None:
        raise RuntimeError("platform database is not configured")
    with connection_pool.connection() as conn:
        yield conn


def execute(sql: str, params: Any = ()) -> None:
    """Fire one statement and commit. Used by the ledger."""
    with connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)


def fetch_all(sql: str, params: Any = ()) -> list[tuple]:
    with connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            return cursor.fetchall()


def reset() -> None:
    """Drop the pool so the next call re-reads the environment. For tests."""
    global _pool, _pool_attempted
    with _lock:
        if _pool is not None:
            try:
                _pool.close()
            except Exception:
                pass
        _pool = None
        _pool_attempted = False
