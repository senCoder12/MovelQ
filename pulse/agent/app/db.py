"""DuckDB warehouse access."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import duckdb

from app.config import get_settings


@contextmanager
def connect(read_only: bool = False) -> Iterator[duckdb.DuckDBPyConnection]:
    """Open a connection to the warehouse, creating the file if needed."""
    settings = get_settings()
    settings.duckdb_path.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(settings.duckdb_path), read_only=read_only)
    try:
        yield conn
    finally:
        conn.close()
