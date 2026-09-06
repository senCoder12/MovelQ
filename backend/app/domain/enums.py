from __future__ import annotations

"""Situation type enum — controlled vocabulary for business situations.

New situation types should only be introduced when there is a concrete
product need, and MUST be accompanied by tests.
"""

from enum import Enum


class SituationType(str, Enum):
    """Controlled enum of business situation types."""

    SHIFT_READINESS_RISK = "SHIFT_READINESS_RISK"
    ROUTE_DISRUPTION = "ROUTE_DISRUPTION"
    VENDOR_RELIABILITY = "VENDOR_RELIABILITY"
    EMPLOYEE_IMPACT_CLUSTER = "EMPLOYEE_IMPACT_CLUSTER"
    SAFETY_SITUATION = "SAFETY_SITUATION"
    DATA_CONFIDENCE = "DATA_CONFIDENCE"


class SituationStatus(str, Enum):
    """Situation lifecycle states."""

    DETECTED = "DETECTED"
    INVESTIGATING = "INVESTIGATING"
    ACTION_RECOMMENDED = "ACTION_RECOMMENDED"
    ACTION_PENDING = "ACTION_PENDING"
    ACTIONED = "ACTIONED"
    VERIFYING = "VERIFYING"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"


class SituationPriority(str, Enum):
    """Situation priority levels."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class ActionType(str, Enum):
    """Possible intervention types."""

    DO_NOTHING = "DO_NOTHING"
    NOTIFY_EMPLOYEES = "NOTIFY_EMPLOYEES"
    ESCALATE_VENDOR = "ESCALATE_VENDOR"
    SIMULATE_VEHICLE_REASSIGNMENT = "SIMULATE_VEHICLE_REASSIGNMENT"
    NODAL_CONVERSION = "NODAL_CONVERSION"


class SignalType(str, Enum):
    """Types of deterministic signals detected from data."""

    TRIP_LATE_START = "TRIP_LATE_START"
    TRIP_LATE_END = "TRIP_LATE_END"
    DELAY_ABOVE_BASELINE = "DELAY_ABOVE_BASELINE"
    NOSHOW_RATE_ELEVATED = "NOSHOW_RATE_ELEVATED"
    ROUTE_REPEATED_DISRUPTION = "ROUTE_REPEATED_DISRUPTION"
    VENDOR_PERFORMANCE_DEGRADED = "VENDOR_PERFORMANCE_DEGRADED"
    ALERT_EPISODE_PERSISTENT = "ALERT_EPISODE_PERSISTENT"
    ACK_LATENCY_HIGH = "ACK_LATENCY_HIGH"
    READINESS_BELOW_THRESHOLD = "READINESS_BELOW_THRESHOLD"
    DATA_INCONSISTENCY = "DATA_INCONSISTENCY"
    SAFETY_EVENT = "SAFETY_EVENT"


class AlertScope(str, Enum):
    """Whether an alert is vehicle-scoped or employee-scoped."""

    VEHICLE = "VEHICLE"
    EMPLOYEE = "EMPLOYEE"


class EpisodeState(str, Enum):
    """State of an alert episode."""

    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"


class EvidenceType(str, Enum):
    """Kinds of evidence in an evidence packet."""

    OBSERVED_FACT = "OBSERVED_FACT"
    HISTORICAL_EVIDENCE = "HISTORICAL_EVIDENCE"
    ESTIMATED_SCENARIO = "ESTIMATED_SCENARIO"
    AI_REASONING = "AI_REASONING"


class DataQualityStatus(str, Enum):
    """Data quality flag status."""

    VALID = "VALID"
    INVALID = "INVALID"
    MISSING = "MISSING"
    SUSPICIOUS = "SUSPICIOUS"
