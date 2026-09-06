from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional

import structlog

from app.domain.entities import AlertEpisode
from app.domain.enums import EpisodeState
from app.domain.interfaces import AlertEpisodeRepository

logger = structlog.get_logger()


class PgEpisodeRepository(AlertEpisodeRepository):
    """Episode repository with in-memory storage for MVP (pluggable to DB)."""

    def __init__(self):
        self._store: Dict[str, AlertEpisode] = {}

    async def save_episode(self, episode: AlertEpisode) -> None:
        self._store[episode.episode_id] = episode

    async def get_episode(self, episode_id: str) -> Optional[AlertEpisode]:
        return self._store.get(episode_id)

    async def get_episodes_for_trip(self, trip_id: int) -> List[AlertEpisode]:
        return [e for e in self._store.values() if e.trip_id == trip_id]

    async def get_active_episodes(
        self,
        business_unit: str,
        trip_date: Optional[date] = None,
    ) -> List[AlertEpisode]:
        return [
            e for e in self._store.values()
            if (not business_unit or e.business_unit == business_unit)
            and e.state == EpisodeState.ACTIVE
        ]

    async def update_episode(self, episode: AlertEpisode) -> None:
        self._store[episode.episode_id] = episode


# Alias for dependency injection
InMemoryEpisodeRepository = PgEpisodeRepository
