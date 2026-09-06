"""Dependency injection wiring for FastAPI routes.

All service instances are created here and injected into route handlers.
This is the composition root — the only place that knows about concrete implementations.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict

# Service instances — initialized at startup or on first access
_services: Dict[str, Any] = {}

# Keeps the seeding task alive for its duration (asyncio only holds a weak
# reference to a task once nothing else refers to it).
_background_tasks: set = set()


def _wire_services() -> None:
    """Instantiate and wire all services and repositories."""
    global _services
    if _services:
        return

    from app.application.services.agent_service import AgentService
    from app.application.services.alert_episode_service import AlertEpisodeService
    from app.application.services.alert_stream_service import AlertStreamService
    from app.application.services.baseline_service import BaselineService
    from app.application.services.decision_service import DecisionService
    from app.application.services.evidence_service import EvidenceService
    from app.application.services.impact_service import ImpactService
    from app.application.services.readiness_service import ReadinessService
    from app.application.services.signal_service import SignalService
    from app.application.services.situation_service import SituationService
    from app.infrastructure.repositories.pg_alert_repository import PgAlertRepository
    from app.infrastructure.repositories.pg_baseline_repository import PgBaselineRepository
    from app.infrastructure.repositories.pg_billing_repository import PgBillingRepository
    from app.infrastructure.repositories.pg_decision_repository import InMemoryDecisionRepository
    from app.infrastructure.repositories.pg_employee_repository import PgEmployeeRepository
    from app.infrastructure.repositories.pg_episode_repository import InMemoryEpisodeRepository
    from app.infrastructure.repositories.pg_situation_repository import InMemorySituationRepository
    from app.infrastructure.repositories.pg_trip_repository import PgTripRepository

    # Repositories
    trip_repo = PgTripRepository()
    employee_repo = PgEmployeeRepository()
    alert_repo = PgAlertRepository()
    baseline_repo = PgBaselineRepository()
    billing_repo = PgBillingRepository()
    episode_repo = InMemoryEpisodeRepository()
    situation_repo = InMemorySituationRepository()
    decision_repo = InMemoryDecisionRepository()

    # Services
    baseline_svc = BaselineService(baseline_repo)
    impact_svc = ImpactService()

    readiness_svc = ReadinessService(
        trip_repository=trip_repo,
        employee_repository=employee_repo,
        baseline_repository=baseline_repo,
    )

    episode_svc = AlertEpisodeService(
        alert_repository=alert_repo,
        episode_repository=episode_repo,
    )

    signal_svc = SignalService()

    situation_svc = SituationService(
        situation_repository=situation_repo,
        episode_repository=episode_repo,
        trip_repository=trip_repo,
        employee_repository=employee_repo,
        signal_service=signal_svc,
        impact_service=impact_svc,
    )

    evidence_svc = EvidenceService(
        trip_repository=trip_repo,
        employee_repository=employee_repo,
        alert_repository=alert_repo,
        baseline_repository=baseline_repo,
        episode_repository=episode_repo,
    )

    decision_svc = DecisionService(
        decision_repository=decision_repo,
        baseline_repository=baseline_repo,
        evidence_service=evidence_svc,
    )

    agent_svc = AgentService(
        evidence_service=evidence_svc,
        situation_repository=situation_repo,
    )

    alert_stream_svc = AlertStreamService(
        trip_repository=trip_repo,
        episode_service=episode_svc,
        signal_service=signal_svc,
        situation_service=situation_svc,
        decision_service=decision_svc,
        agent_service=agent_svc,
    )

    # Store references
    _services["trip_repo"] = trip_repo
    _services["employee_repo"] = employee_repo
    _services["alert_repo"] = alert_repo
    _services["baseline_repo"] = baseline_repo
    _services["billing_repo"] = billing_repo
    _services["episode_repo"] = episode_repo
    _services["situation_repo"] = situation_repo
    _services["decision_repo"] = decision_repo
    _services["readiness_svc"] = readiness_svc
    _services["episode_svc"] = episode_svc
    _services["signal_svc"] = signal_svc
    _services["situation_svc"] = situation_svc
    _services["impact_svc"] = impact_svc
    _services["baseline_svc"] = baseline_svc
    _services["decision_svc"] = decision_svc
    _services["evidence_svc"] = evidence_svc
    _services["agent_svc"] = agent_svc
    _services["alert_stream_svc"] = alert_stream_svc


async def _seed_demo_situations() -> None:
    """Seed initial situations and decisions into memory on server boot."""
    sit_repo = _services.get("situation_repo")
    if not sit_repo or len(getattr(sit_repo, "_store", {})) > 0:
        return

    from app.infrastructure.database import fetch_rows
    from app.application.services.signal_service import SignalService

    sit_svc = _services["situation_svc"]
    ep_svc = _services["episode_svc"]
    dec_svc = _services["decision_svc"]
    trip_repo = _services["trip_repo"]
    sig_svc = _services["signal_svc"]
    agent_svc = _services["agent_svc"]

    import structlog
    logger = structlog.get_logger()

    try:
        sql = """
            SELECT * FROM analytics.v_trip
            WHERE trip_date = '2026-07-15' AND delay_minutes >= 20
            ORDER BY delay_minutes DESC
            LIMIT 15
        """
        rows = await fetch_rows(sql)
        trips = [trip_repo._row_to_trip(dict(r)) for r in rows]

        # Deterministic pass first: DB-bound only, no LLM, so this clears in a
        # couple of seconds and situations are already visible to GET
        # /situations at the end of it. Kept sequential because
        # evaluate_situation's correlation-key dedup (find-then-create/update)
        # isn't safe to run concurrently on the same key.
        created = []
        for trip in trips:
            episodes = await ep_svc.build_episodes_for_trip(trip.trip_id)
            signals = sig_svc.detect_signals(trip, episodes, None, None)
            sit = await sit_svc.evaluate_situation(trip, episodes, signals, None, None)
            if sit:
                await dec_svc.generate_decision(sit)
                created.append(sit)

        # LLM enrichment is independent per situation (~8-10s each via
        # Gemini) -- run all of them concurrently instead of sequentially.
        # This was previously ~150s of sequential awaits inside this one
        # function; on a codebase getting live edits, that's a 150s window
        # for --reload to kill the whole process before a single situation
        # was even saved. Now the situations above are already saved before
        # this starts, so a reload here only costs the enrichment, not the
        # dashboard-visible data.
        async def _enrich(sit) -> None:
            try:
                await agent_svc.investigate_situation(sit.situation_id)
                await sit_svc.mark_action_recommended(sit.situation_id)
            except Exception as e:
                logger.warning("moveiq.seed_enrich_failed", situation_id=sit.situation_id, error=str(e))

        # /home caches its response for 10 minutes (app/core/cache.py). If
        # anyone hit /home before seeding finished, that empty snapshot would
        # otherwise sit there for the full 10 minutes regardless of how many
        # situations just got created.
        from app.core.cache import cache
        cache.delete_pattern("home_dashboard:*")

        await asyncio.gather(*(_enrich(sit) for sit in created))
        cache.delete_pattern("home_dashboard:*")
    except Exception as e:
        logger.warning("moveiq.seed_situations_failed", error=str(e))


async def init_services() -> None:
    """Initialize all service instances during application startup.

    Demo-situation seeding calls the LLM once per seeded situation (up to 15),
    at ~10s each -- awaiting it here would block the whole app from accepting
    any request, including /ask, for minutes on every boot and every
    --reload restart. Run it in the background instead so the API is
    responsive immediately; situations simply populate a little after boot.
    """
    _wire_services()
    task = asyncio.create_task(_seed_demo_situations())
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


def _ensure_services() -> None:
    if not _services:
        _wire_services()


def get_readiness_service():
    _ensure_services()
    return _services["readiness_svc"]

def get_episode_service():
    _ensure_services()
    return _services["episode_svc"]

def get_situation_service():
    _ensure_services()
    return _services["situation_svc"]

def get_decision_service():
    _ensure_services()
    return _services["decision_svc"]

def get_evidence_service():
    _ensure_services()
    return _services["evidence_svc"]

def get_agent_service():
    _ensure_services()
    return _services["agent_svc"]

def get_alert_stream_service():
    _ensure_services()
    return _services["alert_stream_svc"]

def get_trip_repo():
    _ensure_services()
    return _services["trip_repo"]

def get_employee_repo():
    _ensure_services()
    return _services["employee_repo"]

def get_alert_repo():
    _ensure_services()
    return _services["alert_repo"]

def get_baseline_service():
    _ensure_services()
    return _services["baseline_svc"]

def get_billing_repo():
    _ensure_services()
    return _services["billing_repo"]

def get_impact_service():
    _ensure_services()
    return _services["impact_svc"]
