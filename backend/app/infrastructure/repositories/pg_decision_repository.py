from __future__ import annotations

from typing import Dict, List, Optional

import structlog

from app.domain.entities import Action, Decision
from app.domain.interfaces import DecisionRepository

logger = structlog.get_logger()


class PgDecisionRepository(DecisionRepository):
    """Decision repository with in-memory persistence for MVP (pluggable to DB)."""

    def __init__(self):
        self._decisions: Dict[str, Decision] = {}
        self._actions: Dict[str, Action] = {}

    async def save_decision(self, decision: Decision) -> None:
        self._decisions[decision.decision_id] = decision

    async def get_decision(self, decision_id: str) -> Optional[Decision]:
        return self._decisions.get(decision_id)

    async def get_decisions_for_situation(self, situation_id: str) -> List[Decision]:
        return [d for d in self._decisions.values() if d.situation_id == situation_id]

    async def save_action(self, action: Action) -> None:
        self._actions[action.action_id] = action

    async def get_actions_for_situation(self, situation_id: str) -> List[Action]:
        return [a for a in self._actions.values() if a.situation_id == situation_id]


# Alias for dependency injection
InMemoryDecisionRepository = PgDecisionRepository
