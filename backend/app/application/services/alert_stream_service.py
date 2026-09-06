"""Reacts to `important_alert` NOTIFYs from core.fn_notify_important_alert().

This is the app-side half of db/05_alert_stream_trigger.sql. The trigger
already decided the alert is important and put it on the channel; this
service does everything Postgres itself can't do:
  1. run it through the existing Alert Episode -> Signal -> Situation
     pipeline (deterministic, same as the batch/demo path in dependencies.py)
  2. escalate to the LLM via AgentService.investigate_situation
  3. refresh the daily-rollup materialized views the dashboard reads
The situation lands in SituationRepository as a side effect of step 1,
which is what makes it show up on the dashboard on the next poll.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import structlog

from app.application.services.agent_service import AgentService
from app.application.services.alert_episode_service import AlertEpisodeService
from app.application.services.decision_service import DecisionService
from app.application.services.signal_service import SignalService
from app.application.services.situation_service import SituationService
from app.core.cache import cache
from app.domain.interfaces import TripRepository
from app.infrastructure.database import execute

logger = structlog.get_logger(__name__)

# Daily rollups the dashboard's home/readiness views read. Both carry the
# unique index REFRESH ... CONCURRENTLY needs (03_analytics_layer.sql).
_MATERIALIZED_VIEWS_TO_REFRESH = (
    "analytics.mv_daily_alert_metrics",
    "analytics.mv_daily_trip_metrics",
)


class AlertStreamService:
    def __init__(
        self,
        trip_repository: TripRepository,
        episode_service: AlertEpisodeService,
        signal_service: SignalService,
        situation_service: SituationService,
        decision_service: DecisionService,
        agent_service: AgentService,
    ):
        self.trip_repository = trip_repository
        self.episode_service = episode_service
        self.signal_service = signal_service
        self.situation_service = situation_service
        self.decision_service = decision_service
        self.agent_service = agent_service

    async def handle_notification(self, payload: Dict[str, Any]) -> None:
        event_id = payload.get("event_id")
        trip_id = payload.get("trip_id")
        logger.info("alert_stream.notification_received", event_id=event_id, trip_id=trip_id)

        trip = await self.trip_repository.get_trip(trip_id) if trip_id else None

        if trip is None:
            # ~72% of alerts have no matching fact_trip (see 02_core_model.sql's
            # note on trip_is_orphan). SituationService.evaluate_situation is
            # built around a Trip, so an orphan alert can't go through the
            # normal Episode -> Signal -> Situation path without fabricating
            # trip data. Surface it in logs/alerting instead of forcing it
            # through the pipeline; if orphan safety alerts need a dashboard
            # entry too, that needs a Situation variant that doesn't require
            # a trip, which is a product decision, not something to guess at.
            logger.warning(
                "alert_stream.orphan_trip_skipped",
                event_id=event_id,
                trip_id=trip_id,
                event_type=payload.get("event_type"),
            )
            return

        episodes = await self.episode_service.build_episodes_for_trip(trip_id)
        signals = self.signal_service.detect_signals(trip, episodes, None, None)

        situation = await self.situation_service.evaluate_situation(
            trip, episodes, signals, None, None
        )
        if situation is None:
            logger.info("alert_stream.no_situation_created", event_id=event_id, trip_id=trip_id)
            await self._refresh_dashboard_views()
            return

        await self.decision_service.generate_decision(situation)

        investigation = await self.agent_service.investigate_situation(situation.situation_id)
        logger.info(
            "alert_stream.llm_investigation_complete",
            situation_id=situation.situation_id,
            mode=investigation.get("mode", "llm"),
        )
        await self.situation_service.mark_action_recommended(situation.situation_id)

        await self._refresh_dashboard_views()

    async def _refresh_dashboard_views(self) -> None:
        for view in _MATERIALIZED_VIEWS_TO_REFRESH:
            try:
                await execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view}")
            except Exception as e:
                logger.warning("alert_stream.mv_refresh_failed", view=view, error=str(e))

        # /home caches its response for 10 minutes (app/core/cache.py) and was
        # previously only invalidated by take_action() in situations.py -- a
        # brand new situation from this pipeline would otherwise sit unseen
        # on the Home page for up to 10 minutes even with the frontend polling.
        cleared = cache.delete_pattern("home_dashboard:*")
        logger.info("alert_stream.home_cache_invalidated", entries_cleared=cleared)
