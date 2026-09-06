"""Guardrail for LLM-generated SQL.

The agent is only ever shown the `analytics` schema (see
db/03_analytics_layer.sql) -- one read-only view per grain, no write
surface. But the app's own Postgres credentials are not scoped that way
(they're the Neon owner role), so the LLM's SQL is never trusted at face
value: this module re-checks every generated query before it reaches the
database, independent of whatever the prompt asked for.
"""

from __future__ import annotations

import re

_ALLOWED_SCHEMA = "analytics"

_FORBIDDEN_KEYWORDS = re.compile(
    r"\b(insert|update|delete|drop|alter|truncate|grant|revoke|create|"
    r"call|execute|copy|merge|vacuum|comment|listen|notify|do|refresh)\b",
    re.IGNORECASE,
)

_TABLE_REF = re.compile(r"\b(?:from|join)\s+([a-zA-Z_][a-zA-Z0-9_.\"]*)", re.IGNORECASE)


def is_safe_select(sql: str) -> bool:
    """True only for a single read-only SELECT touching analytics.* views."""
    if not sql or not isinstance(sql, str):
        return False

    stripped = sql.strip().rstrip(";").strip()
    if not stripped or ";" in stripped:
        return False  # no statement chaining

    if not re.match(r"^(select|with)\b", stripped, re.IGNORECASE):
        return False

    if _FORBIDDEN_KEYWORDS.search(stripped):
        return False

    tables = _TABLE_REF.findall(stripped)
    if not tables:
        return False

    for table in tables:
        if not table.strip('"').lower().startswith(f"{_ALLOWED_SCHEMA}."):
            return False

    return True


def enforce_limit(sql: str, default_limit: int = 200) -> str:
    """Append a LIMIT if the query doesn't already cap its result set."""
    stripped = sql.strip().rstrip(";").strip()
    if re.search(r"\blimit\s+\d+\b", stripped, re.IGNORECASE):
        return stripped
    return f"{stripped}\nLIMIT {default_limit}"
