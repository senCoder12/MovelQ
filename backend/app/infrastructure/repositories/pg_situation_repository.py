from __future__ import annotations

from typing import Dict, List, Optional

import structlog

from app.domain.entities import Situation
from app.domain.interfaces import SituationRepository

logger = structlog.get_logger()


class PgSituationRepository(SituationRepository):
    """Situation repository with in-memory persistence for MVP (pluggable to DB)."""

    def __init__(self):
        self._store: Dict[str, Situation] = {}

    async def save_situation(self, situation: Situation) -> None:
        self._store[situation.situation_id] = situation

    async def get_situation(self, situation_id: str) -> Optional[Situation]:
        return self._store.get(situation_id)

    async def get_situations(
        self,
        business_unit: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[Situation]:
        res = list(self._store.values())
        if business_unit:
            res = [s for s in res if s.business_unit == business_unit]
        if status:
            res = [s for s in res if s.status.value == status]

        # Sort by updated_at descending or priority
        priority_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}
        res.sort(key=lambda s: priority_order.get(s.priority.value, 99))
        return res[:limit]

    async def find_by_correlation_key(self, correlation_key: str) -> Optional[Situation]:
        for s in self._store.values():
            if s.correlation_key == correlation_key:
                return s
        return None

    async def update_situation(self, situation: Situation) -> None:
        self._store[situation.situation_id] = situation


# Alias for dependency injection
InMemorySituationRepository = PgSituationRepository
