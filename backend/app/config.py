"""Centralized configuration for MoveIQ.

All configurable values live here. No magic numbers in business logic.
Uses Pydantic Settings for type-safe environment variable loading.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # ── Application ──────────────────────────────────────────────
    app_name: str = "moveiq"
    app_port: int = 8000
    debug: bool = False
    demo_mode: bool = True

    # ── Database (Neon PostgreSQL) ───────────────────────────────
    neon_database_url: str = "postgresql://localhost/moveiq"
    db_pool_min: int = 2
    db_pool_max: int = 10

    # Neon's pooled connection above goes through PgBouncer in
    # transaction mode, which does not reliably deliver LISTEN/NOTIFY
    # (a session can be handed to a different client between LISTEN
    # and the NOTIFY arriving). This must be Neon's *direct* connection
    # string (no "-pooler" in the host), held open on one dedicated
    # connection for the alert stream listener. Falls back to
    # neon_database_url if unset, with a startup warning, so the app
    # still boots in dev -- but that fallback is not safe for production.
    neon_direct_database_url: str = ""

    # ── LLM Configuration ───────────────────────────────────────
    llm_api_key: str = ""
    llm_model: str = "gpt-4o"
    llm_temperature: float = 0.3
    llm_max_tokens: int = 4096
    llm_cache_ttl_seconds: int = 3600
    llm_max_calls_per_hour: int = 100

    # ── Alert Episode Engine ────────────────────────────────────
    alert_episode_gap_minutes: int = 15

    # ── Situation Engine ────────────────────────────────────────
    situation_time_window_hours: int = 4

    # ── Readiness Engine ────────────────────────────────────────
    readiness_threshold_warning: float = 0.85
    readiness_threshold_critical: float = 0.75

    # ── Material Change Detection ───────────────────────────────
    material_change_threshold_pp: float = 5.0  # percentage points

    # ── Historical Baseline ─────────────────────────────────────
    baseline_lookback_7d: int = 7
    baseline_lookback_30d: int = 30
    baseline_lookback_90d: int = 90
    baseline_min_sample_size: int = 10

    # ── Replay Engine ───────────────────────────────────────────
    replay_speed: float = 1.0
    replay_default_date: str = "2026-07-15"

    # ── Context Builder ─────────────────────────────────────────
    context_max_evidence_items: int = 20
    context_max_token_budget: int = 8000

    # ── SLA Definition ──────────────────────────────────────────
    sla_on_time_minutes: int = 15
    sla_late_thresholds: list[int] = [5, 10, 15, 30]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
