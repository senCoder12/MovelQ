"""Repository interfaces — abstract contracts for data access.

Domain code depends on these interfaces, never on concrete database implementations.
Infrastructure implementations (pg_*_repository.py) can be swapped without changing
business logic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Any

from app.domain.entities import (
    Action,
    Alert,
    AlertEpisode,
    Decision,
    EmployeeTrip,
    HistoricalBaseline,
    ShiftReadiness,
    Signal,
    Situation,
    Trip,
)


class TripRepository(ABC):
    """Access to trip data."""

    @abstractmethod
    async def get_trip(self, trip_id: int) -> Trip | None: ...

    @abstractmethod
    async def get_trips_for_shift(
        self,
        business_unit: str,
        office: str,
        shift: str,
        direction: str,
        trip_date: date,
    ) -> list[Trip]: ...

    @abstractmethod
    async def get_trip_count(
        self,
        business_unit: str | None = None,
        office: str | None = None,
        trip_date: date | None = None,
    ) -> int: ...

    @abstractmethod
    async def get_shift_summary(
        self,
        business_unit: str,
        office: str,
        trip_date: date,
    ) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def get_delay_distribution(
        self,
        business_unit: str,
        office: str,
        shift: str | None = None,
        direction: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> dict[str, Any]: ...

    @abstractmethod
    async def get_vendor_metrics(
        self,
        business_unit: str,
        office: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def get_route_metrics(
        self,
        business_unit: str,
        office: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[dict[str, Any]]: ...


class EmployeeRepository(ABC):
    """Access to employee trip leg data."""

    @abstractmethod
    async def get_employees_for_trip(self, trip_id: int) -> list[EmployeeTrip]: ...

    @abstractmethod
    async def get_employees_for_shift(
        self,
        business_unit: str,
        office: str,
        shift: str,
        direction: str | None = None,
        trip_date: date | None = None,
    ) -> list[EmployeeTrip]: ...

    @abstractmethod
    async def get_affected_employees(self, trip_ids: list[int]) -> list[EmployeeTrip]: ...

    @abstractmethod
    async def get_shift_employee_stats(
        self,
        business_unit: str,
        office: str,
        shift: str,
        direction: str,
        trip_date: date,
    ) -> dict[str, Any]: ...


class AlertRepository(ABC):
    """Access to alert data."""

    @abstractmethod
    async def get_alerts_for_trip(self, trip_id: int) -> list[Alert]: ...

    @abstractmethod
    async def get_alerts_for_date(
        self,
        business_unit: str,
        alert_date: date,
    ) -> list[Alert]: ...

    @abstractmethod
    async def get_alert_counts_by_type(
        self,
        business_unit: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[dict[str, Any]]: ...


class AlertEpisodeRepository(ABC):
    """Persistence for computed alert episodes."""

    @abstractmethod
    async def save_episode(self, episode: AlertEpisode) -> None: ...

    @abstractmethod
    async def get_episode(self, episode_id: str) -> AlertEpisode | None: ...

    @abstractmethod
    async def get_episodes_for_trip(self, trip_id: int) -> list[AlertEpisode]: ...

    @abstractmethod
    async def get_active_episodes(
        self,
        business_unit: str,
        trip_date: date | None = None,
    ) -> list[AlertEpisode]: ...

    @abstractmethod
    async def update_episode(self, episode: AlertEpisode) -> None: ...


class SituationRepository(ABC):
    """Persistence for business situations."""

    @abstractmethod
    async def save_situation(self, situation: Situation) -> None: ...

    @abstractmethod
    async def get_situation(self, situation_id: str) -> Situation | None: ...

    @abstractmethod
    async def get_situations(
        self,
        business_unit: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[Situation]: ...

    @abstractmethod
    async def find_by_correlation_key(self, correlation_key: str) -> Situation | None: ...

    @abstractmethod
    async def update_situation(self, situation: Situation) -> None: ...


class DecisionRepository(ABC):
    """Persistence for decisions and actions."""

    @abstractmethod
    async def save_decision(self, decision: Decision) -> None: ...

    @abstractmethod
    async def get_decision(self, decision_id: str) -> Decision | None: ...

    @abstractmethod
    async def get_decisions_for_situation(self, situation_id: str) -> list[Decision]: ...

    @abstractmethod
    async def save_action(self, action: Action) -> None: ...

    @abstractmethod
    async def get_actions_for_situation(self, situation_id: str) -> list[Action]: ...


class BaselineRepository(ABC):
    """Access to historical baselines."""

    @abstractmethod
    async def get_baseline(
        self,
        metric_name: str,
        office: str,
        shift: str | None = None,
        direction: str | None = None,
        period_label: str = "30d",
    ) -> HistoricalBaseline | None: ...

    @abstractmethod
    async def get_shift_baseline(
        self,
        business_unit: str,
        office: str,
        shift: str,
        direction: str,
        lookback_days: int = 30,
        reference_date: date | None = None,
    ) -> dict[str, Any]: ...

    @abstractmethod
    async def save_baseline(self, baseline: HistoricalBaseline) -> None: ...


class BillingRepository(ABC):
    """Access to billing data."""

    @abstractmethod
    async def get_cost_for_trips(self, trip_ids: list[int]) -> dict[str, Any]: ...

    @abstractmethod
    async def get_vendor_cost_metrics(
        self,
        business_unit: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[dict[str, Any]]: ...


class LLMProvider(ABC):
    """Abstract interface for LLM calls.

    Current: OpenAI adapter. Future: multiple providers / model routing.
    """

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str: ...

    @abstractmethod
    async def generate_with_tools(
        self,
        prompt: str,
        tools: list[dict[str, Any]],
        system_prompt: str | None = None,
    ) -> dict[str, Any]: ...
