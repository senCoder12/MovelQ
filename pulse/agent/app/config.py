"""Runtime configuration, loaded from environment / .env."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field

# agent/app/config.py -> agent/app -> agent -> <repo root>
REPO_ROOT = Path(__file__).resolve().parents[2]

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
# The token ledger needs the platform database, and those credentials already live
# in exactly one gitignored file -- backend/.env, which DotenvEnvironmentPostProcessor
# reads on the Java side. Loading it here too means one file to fill in rather than
# the same Neon URI pasted into two. agent/.env is loaded first and wins, so the
# agent can still be pointed at a different database when that is wanted.
load_dotenv(REPO_ROOT / "backend" / ".env")


def _path(env_key: str, default: str) -> Path:
    """Resolve a configured path, relative paths anchored at the repo root."""
    value = Path(os.getenv(env_key, default))
    return value if value.is_absolute() else REPO_ROOT / value


def _flag(env_key: str, default: bool) -> bool:
    """Read a boolean env var at call time. Absent means the default."""
    raw = os.getenv(env_key)
    if raw is None:
        return default
    return raw.strip().lower() not in ("false", "0", "no", "off")


class Settings(BaseModel):
    app_name: str = os.getenv("APP_NAME", "pulse-agent")
    version: str = "0.1.0"
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))
    duckdb_path: Path = _path("DUCKDB_PATH", "data/warehouse.duckdb")
    raw_data_dir: Path = _path("RAW_DATA_DIR", "data/raw")
    llm_api_key: str | None = os.getenv("LLM_API_KEY") or None
    llm_model: str = os.getenv("LLM_MODEL", "gemini-2.5-pro")
    # pulse.llm.enabled -- when false, the two model call sites short-circuit to
    # their template paths instead of dialling out. Distinct from an absent
    # llm_api_key, which degrades the same way but only after a failed attempt:
    # this is a declared operating mode, not a fault, and it is what
    # tests/test_degraded_mode.py exercises.
    # default_factory, not a plain default: every other field here evaluates
    # os.getenv once at class-definition time, which is fine for values fixed at
    # boot but makes this one untestable -- a test that sets PULSE_LLM_ENABLED
    # and rebuilds Settings would still read the value baked in at import.
    llm_enabled: bool = Field(default_factory=lambda: _flag("PULSE_LLM_ENABLED", True))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
