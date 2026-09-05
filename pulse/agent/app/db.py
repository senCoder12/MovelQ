"""DuckDB warehouse access.

Multi-tenancy is enforced here, not by convention in calling code: every
read goes through ``fetch_df``/``fetch_one``, which take tenant_id as
their first positional argument, reject a missing/empty tenant_id
outright, and bind it as the first parameter of the query. Callers are
expected to write their SQL with ``WHERE tenant_id = ?`` as the query's
first placeholder (app/metrics/compiler.py does this for every generated
metric query) -- these helpers are the one place that validates the
tenant scope is actually present before anything touches the database.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator, Sequence

import duckdb
import pandas as pd

from app.config import get_settings


@contextmanager
def connect(read_only: bool = False) -> Iterator[duckdb.DuckDBPyConnection]:
    """Open a connection to the warehouse, creating the file if needed.

    Unscoped: used by the ingest pipeline to build the warehouse itself,
    where there is no single tenant to scope to.
    """
    settings = get_settings()
    settings.duckdb_path.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(settings.duckdb_path), read_only=read_only)
    try:
        yield conn
    finally:
        conn.close()


def _require_tenant(tenant_id: str) -> str:
    if not tenant_id or not str(tenant_id).strip():
        raise ValueError("tenant_id is required and cannot be None or empty")
    return tenant_id


def fetch_df(tenant_id: str, sql: str, params: Sequence[Any] = ()) -> pd.DataFrame:
    """Run a tenant-scoped query and return the result as a DataFrame.

    ``sql`` must place its tenant filter (``WHERE tenant_id = ?``) as the
    first ``?`` placeholder; ``tenant_id`` is bound there, ``params``
    fill the remaining placeholders in order.
    """
    _require_tenant(tenant_id)
    with connect(read_only=True) as conn:
        return conn.execute(sql, [tenant_id, *params]).fetchdf()


def fetch_one(tenant_id: str, sql: str, params: Sequence[Any] = ()) -> tuple | None:
    """Run a tenant-scoped query and return the first row, or None."""
    _require_tenant(tenant_id)
    with connect(read_only=True) as conn:
        return conn.execute(sql, [tenant_id, *params]).fetchone()
