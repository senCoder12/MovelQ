from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

import structlog
from pydantic import BaseModel, Field

from app.config import get_settings

logger = structlog.get_logger(__name__)


class TripReplayResult(BaseModel):
    trip_id: int
    alerts: List[Dict[str, Any]] = Field(default_factory=list)
    episodes: List[Dict[str, Any]] = Field(default_factory=list)
    signals: List[Dict[str, Any]] = Field(default_factory=list)
    situation: Optional[Dict[str, Any]] = None
    timeline: List[Dict[str, Any]] = Field(default_factory=list)


class ReplayResult(BaseModel):
    date: date
    trips_processed: int = 0
    episodes_created: int = 0
    signals_detected: int = 0
    situations_created: int = 0
    situations_updated: int = 0
    llm_calls: int = 0
    readiness_scores: List[Dict[str, Any]] = Field(default_factory=list)
    situations: List[Dict[str, Any]] = Field(default_factory=list)


class ReplayEngine:
    """Processes historical data as though events occurred over time.

    The replay engine allows demonstrating the full agentic loop:
    T0: trip begins
    T1: raw alerts appear
    T2: alerts become episodes
    T3: delay/employee impact changes
    T4: episode contributes to situation
    T5: situation becomes high priority
    T6: LLM investigates
    T7: recommendation generated
    T8: manager action selected
    T9: outcome verified
    """

    def __init__(
        self,
        trip_repo: Any = None,
        alert_repo: Any = None,
        employee_repo: Any = None,
        episode_service: Any = None,
        situation_service: Any = None,
        agent_service: Any = None,
    ):
        self.trip_repo = trip_repo
        self.alert_repo = alert_repo
        self.employee_repo = employee_repo
        self.episode_service = episode_service
        self.situation_service = situation_service
        self.agent_service = agent_service

        self.settings = get_settings()
        self.current_time = None
        self.speed = self.settings.replay_speed
        self.state = "STOPPED"

    async def set_date(self, target_date: date):
        """Set the replay to a specific date."""
        self.state = "STOPPED"
        logger.info("replay.set_date", target_date=target_date)

    async def process_date(self, target_date: date) -> ReplayResult:
        """Process all events for a given date and return results."""
        logger.info("replay.process_date", target_date=target_date)

        return ReplayResult(
            date=target_date,
            trips_processed=0,
            episodes_created=0,
            signals_detected=0,
            situations_created=0,
            situations_updated=0,
            llm_calls=0,
            readiness_scores=[],
            situations=[],
        )

    async def process_trip(self, trip_id: int) -> TripReplayResult:
        """Process a single trip through the full pipeline."""
        logger.info("replay.process_trip", trip_id=trip_id)

        return TripReplayResult(
            trip_id=trip_id,
            alerts=[],
            episodes=[],
            signals=[],
            situation=None,
            timeline=[],
        )
