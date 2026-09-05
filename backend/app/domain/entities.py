"""Domain entities — typed Pydantic models for all core business concepts.

Every domain concept has an explicit model. No raw dictionaries.
Compatible with Python 3.9+.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.domain.enums import (
    ActionType,
    AlertScope,
    DataQualityStatus,
    EpisodeState,
    EvidenceType,
    SignalType,
    SituationPriority,
    SituationStatus,
    SituationType,
)


class MoveIQBaseModel(BaseModel):
    """Base model that ignores extra fields from database queries."""
    model_config = {"extra": "ignore"}


# ── Trip ─────────────────────────────────────────────────────────

class Trip(MoveIQBaseModel):
    """One trip — the primary operational spine."""

    trip_id: int
    trip_date: date
    business_unit: str
    office: str
    vendor: Optional[str] = None
    shift: Optional[str] = None
    shift_band: Optional[str] = None
    product_type: Optional[str] = None
    trip_direction: Optional[str] = None
    trip_nodal: Optional[str] = None
    route_source: Optional[str] = None
    delay_reason: Optional[str] = None
    actual_escort: Optional[bool] = None
    is_driver_nc: Optional[bool] = None
    is_cab_nc: Optional[bool] = None

    planned_km: Optional[float] = None
    traveled_km: Optional[float] = None
    km_variance: Optional[float] = None

    planned_start_ts: Optional[datetime] = None
    actual_start_ts: Optional[datetime] = None
    planned_duration_min: Optional[int] = None
    actual_duration_min: Optional[int] = None
    delay_minutes: Optional[int] = None

    planned_employee_cnt: Optional[int] = None
    actual_employee_cnt: Optional[int] = None
    riders_actual: Optional[int] = None
    noshow_cnt: Optional[int] = None
    capacity_utilisation: Optional[float] = None

    is_delayed: bool = False
    is_on_time: bool = True
    dq_flags: List[str] = Field(default_factory=list)


# ── Employee Trip Leg ────────────────────────────────────────────

class EmployeeTrip(MoveIQBaseModel):
    """One employee leg on one trip."""

    leg_key: Optional[int] = None
    trip_id: int
    stwid: Optional[int] = None
    gender: Optional[str] = None
    emp_role: Optional[str] = None
    trip_date: date
    business_unit: str
    office: Optional[str] = None
    shift: Optional[str] = None
    shift_band: Optional[str] = None
    product_type: Optional[str] = None
    boarding_status: Optional[str] = None
    not_boarding_reason: Optional[str] = None
    is_no_show: bool = False
    pickup_delay_min: Optional[int] = None
    is_late_pickup: bool = False


# ── Alert ────────────────────────────────────────────────────────

class Alert(MoveIQBaseModel):
    """One raw alert event."""

    event_id: str
    trip_id: int
    stwid: Optional[int] = None
    business_unit: str
    alert_date: Optional[date] = None
    event_type: str
    alert_scope: AlertScope
    severity_raw: str
    severity: Optional[str] = None  # Only Sev-1/2/3, None otherwise
    was_triaged: bool = False
    resolution_path: Optional[str] = None
    start_ts: datetime
    acknowledge_ts: Optional[datetime] = None
    ack_latency_min: Optional[int] = None
    state_text: Optional[str] = None
    source: Optional[str] = None


# ── Alert Episode ────────────────────────────────────────────────

class AlertEpisode(MoveIQBaseModel):
    """A group of correlated raw alerts forming one episode.

    Primary correlation key: business_unit + trip_id + event_type + source.
    Alerts within ALERT_EPISODE_GAP_MINUTES of each other join the same episode.
    """

    episode_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    business_unit: str
    trip_id: int
    event_type: str
    source: Optional[str] = None
    first_seen: datetime
    last_seen: datetime
    occurrence_count: int = 1
    duration_minutes: float = 0.0
    severity_summary: Dict[str, int] = Field(default_factory=dict)
    ack_latency_summary: Dict[str, Optional[float]] = Field(default_factory=dict)
    raw_alert_ids: List[str] = Field(default_factory=list)
    state: EpisodeState = EpisodeState.ACTIVE
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ── Signal ───────────────────────────────────────────────────────

class Signal(MoveIQBaseModel):
    """A meaningful deterministic observation — not yet a manager-facing incident."""

    signal_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    signal_type: SignalType
    business_unit: str
    trip_id: Optional[int] = None
    office: Optional[str] = None
    shift: Optional[str] = None
    direction: Optional[str] = None
    description: str
    value: Optional[float] = None
    threshold: Optional[float] = None
    baseline_value: Optional[float] = None
    evidence_type: EvidenceType = EvidenceType.OBSERVED_FACT
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ── Situation ────────────────────────────────────────────────────

class SituationImpact(MoveIQBaseModel):
    """Quantified impact of a situation."""

    affected_employees: int = 0
    affected_trips: int = 0
    affected_routes: int = 0
    delay_minutes_total: int = 0
    delay_p95: Optional[float] = None
    historical_delay_p95: Optional[float] = None
    readiness_delta_pp: Optional[float] = None
    cost_impact: Optional[float] = None
    noshow_count: int = 0


class Situation(MoveIQBaseModel):
    """A meaningful business situation — the core domain entity.

    A situation is a living entity that tracks lifecycle from detection
    through resolution. It is created only when signals/episodes have
    genuine business impact.
    """

    situation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    situation_type: SituationType
    status: SituationStatus = SituationStatus.DETECTED
    priority: SituationPriority = SituationPriority.MEDIUM
    title: str = ""
    description: str = ""
    business_unit: str
    office: Optional[str] = None
    shift: Optional[str] = None
    direction: Optional[str] = None
    trip_ids: List[int] = Field(default_factory=list)
    route_ids: List[str] = Field(default_factory=list)

    impact: SituationImpact = Field(default_factory=SituationImpact)
    supporting_signal_ids: List[str] = Field(default_factory=list)
    supporting_episode_ids: List[str] = Field(default_factory=list)

    historical_context: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = 1.0

    recommended_actions: List[str] = Field(default_factory=list)
    current_action: Optional[str] = None
    outcome: Optional[str] = None

    first_seen: datetime = Field(default_factory=datetime.utcnow)
    last_seen: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Deduplication correlation key
    @property
    def correlation_key(self) -> str:
        """Unique key for deduplication. Centralized here, never scattered."""
        parts = [
            self.business_unit,
            self.office or "",
            self.shift or "",
            self.direction or "",
            self.situation_type.value,
        ]
        return "|".join(parts)


# ── Decision & Action ───────────────────────────────────────────

class ActionOption(MoveIQBaseModel):
    """One candidate action in a decision comparison."""

    action_type: ActionType
    description: str
    expected_impact: str
    estimated_cost: str = "Low"
    confidence: str = "Medium"
    supporting_evidence: List[str] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    evidence_type: EvidenceType = EvidenceType.HISTORICAL_EVIDENCE


class Decision(MoveIQBaseModel):
    """A decision comparison for a situation."""

    decision_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    situation_id: str
    options: List[ActionOption] = Field(default_factory=list)
    recommended_action: Optional[ActionType] = None
    recommendation_reasoning: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Action(MoveIQBaseModel):
    """A recorded action taken on a situation."""

    action_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    situation_id: str
    decision_id: str
    action_type: ActionType
    executed_by: str = "system"
    executed_at: datetime = Field(default_factory=datetime.utcnow)
    outcome: Optional[str] = None
    outcome_verified: bool = False
    outcome_label: str = "UNAVAILABLE"  # SIMULATED | VERIFIED | UNAVAILABLE


# ── Evidence Packet ──────────────────────────────────────────────

class EvidencePacket(MoveIQBaseModel):
    """Compact, structured evidence sent to the LLM.

    Never contains raw CSV rows, employee PII, or precise locations.
    """

    situation: Dict[str, Any]
    shift_context: Dict[str, Any] = Field(default_factory=dict)
    current_state: Dict[str, Any] = Field(default_factory=dict)
    historical_context: Dict[str, Any] = Field(default_factory=dict)
    alert_context: Dict[str, Any] = Field(default_factory=dict)
    root_cause_evidence: Dict[str, Any] = Field(default_factory=dict)
    workforce_impact: Dict[str, Any] = Field(default_factory=dict)
    future_risk: Dict[str, Any] = Field(default_factory=dict)
    recommendation_context: Dict[str, Any] = Field(default_factory=dict)
    data_confidence: Dict[str, Any] = Field(default_factory=dict)

    context_version: str = ""
    last_updated_at: datetime = Field(default_factory=datetime.utcnow)
    evidence_hash: str = ""


# ── Data Quality ─────────────────────────────────────────────────

class DataQualityIssue(MoveIQBaseModel):
    """A specific data quality problem."""

    field: str
    raw_value: Optional[str] = None
    normalized_value: Any = None
    quality_status: DataQualityStatus
    reason: str


# ── Historical Baseline ─────────────────────────────────────────

class HistoricalBaseline(MoveIQBaseModel):
    """A calculated baseline for comparison."""

    scope: str  # e.g., "office:Oakmont|shift:03:00|direction:LOGIN"
    metric_name: str
    period_label: str  # "7d", "30d", "90d"
    mean: Optional[float] = None
    median: Optional[float] = None
    p90: Optional[float] = None
    p95: Optional[float] = None
    p99: Optional[float] = None
    sample_size: int = 0
    calculated_at: datetime = Field(default_factory=datetime.utcnow)


# ── Shift Readiness ──────────────────────────────────────────────

class ShiftReadiness(MoveIQBaseModel):
    """Shift readiness calculation result — deterministic and explainable."""

    office: str
    shift: str
    direction: str
    business_unit: str
    trip_date: date

    employees_expected: int = 0
    employees_ready_on_time: int = 0
    employees_late: int = 0
    employees_noshow: int = 0
    employees_at_risk: int = 0

    readiness_score: float = 0.0  # employees_ready_on_time / employees_expected
    historical_baseline: Optional[float] = None
    delta_pp: Optional[float] = None  # percentage points difference

    affected_trips: int = 0
    affected_routes: int = 0
    top_contributing_situation: Optional[str] = None

    on_time_rate: Optional[float] = None
    avg_delay_minutes: Optional[float] = None
    p90_delay_minutes: Optional[float] = None
    p95_delay_minutes: Optional[float] = None
