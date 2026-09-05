"""Runtime configuration, loaded from environment / .env."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel

# agent/app/config.py -> agent/app -> agent -> <repo root>
REPO_ROOT = Path(__file__).resolve().parents[2]

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def _path(env_key: str, default: str) -> Path:
    """Resolve a configured path, relative paths anchored at the repo root."""
    value = Path(os.getenv(env_key, default))
    return value if value.is_absolute() else REPO_ROOT / value


class Settings(BaseModel):
    app_name: str = os.getenv("APP_NAME", "pulse-agent")
    version: str = "0.1.0"
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))
    duckdb_path: Path = _path("DUCKDB_PATH", "data/warehouse.duckdb")
    raw_data_dir: Path = _path("RAW_DATA_DIR", "data/raw")
    llm_api_key: str | None = os.getenv("LLM_API_KEY") or None
    llm_model: str = os.getenv("LLM_MODEL", "claude-opus-5")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
