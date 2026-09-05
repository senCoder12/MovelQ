from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Dict, Optional

import structlog

from app.domain.entities import EvidencePacket, Situation
from app.domain.interfaces import (
    AlertEpisodeRepository,
    AlertRepository,
    BaselineRepository,
    EmployeeRepository,
    TripRepository,
)

logger = structlog.get_logger(__name__)


class EvidenceService:
    """Evidence Builder for LLM reasoning.

    Assembles compact, structured, privacy-safe evidence packets.
    Strictly excludes all employee PII (names, phone numbers, email, addresses, coordinates).
    """

    def __init__(
        self,
        trip_repository: Optional[TripRepository] = None,
        employee_repository: Optional[EmployeeRepository] = None,
        alert_repository: Optional[AlertRepository] = None,
        baseline_repository: Optional[BaselineRepository] = None,
        episode_repository: Optional[AlertEpisodeRepository] = None,
    ):
        self.trip_repository = trip_repository
        self.employee_repository = employee_repository
        self.alert_repository = alert_repository
        self.baseline_repository = baseline_repository
        self.episode_repository = episode_repository

    async def build_evidence_packet(self, situation: Situation) -> EvidencePacket:
        logger.info("evidence.build_packet", situation_id=situation.situation_id)

        # 1. Situation block
        situation_data = {
            "situation_id": situation.situation_id,
            "type": situation.situation_type.value,
            "priority": situation.priority.value,
            "status": situation.status.value,
            "title": situation.title,
            "description": situation.description,
            "business_unit": situation.business_unit,
            "office": situation.office,
            "shift": situation.shift,
            "direction": situation.direction,
        }

        # 2. Shift context
        shift_context = {
            "office": situation.office or "Oakmont",
            "shift": situation.shift or "03:00",
            "direction": situation.direction or "LOGIN",
            "business_unit": situation.business_unit,
        }

        # 3. Current state
        current_state = {
            "affected_employees": situation.impact.affected_employees,
            "affected_trips": situation.impact.affected_trips,
            "affected_routes": situation.impact.affected_routes,
            "delay_minutes_total": situation.impact.delay_minutes_total,
            "delay_p95_minutes": situation.impact.delay_p95,
            "noshow_count": situation.impact.noshow_count,
        }

        # 4. Historical context
        hist_p90 = situation.impact.historical_delay_p95 or 8.0
        historical_context = {
            "historical_delay_p90_minutes": hist_p90,
            "readiness_delta_pp": situation.impact.readiness_delta_pp,
            "recurrence_recent_count": len(situation.supporting_episode_ids),
        }

        # 5. Alert context (episode summaries, NEVER raw alerts)
        alert_context = {
            "active_episode_count": len(situation.supporting_episode_ids),
            "episodes_referenced": situation.supporting_episode_ids,
        }

        # 6. Root cause evidence
        root_cause_evidence = {
            "primary_factors": [
                f"{situation.situation_type.value} operational signals triggered threshold",
                f"Recorded cumulative delay of {situation.impact.delay_minutes_total}m across impacted routes",
            ],
            "contributing_vendor": "Vendor Dispatch Desk",
        }

        # 7. Workforce impact (Privacy-safe: counts only, ZERO PII)
        workforce_impact = {
            "employees_expected": situation.impact.affected_employees,
            "employees_at_risk": situation.impact.affected_employees,
            "noshow_count": situation.impact.noshow_count,
            "readiness_impact_level": situation.priority.value,
        }

        # 8. Future risk
        future_risk = {
            "downstream_shift_risk": "Moderate" if situation.impact.delay_minutes_total > 15 else "Low",
            "estimated_recovery_time_minutes": max(10, (situation.impact.delay_minutes_total or 15) - 5),
            "confidence": "MEDIUM",
        }

        # 9. Recommendation context
        recommendation_context = {
            "candidate_actions": situation.recommended_actions,
            "preferred_action": situation.recommended_actions[0] if situation.recommended_actions else "DO_NOTHING",
        }

        # 10. Data confidence
        data_confidence = {
            "evidence_coverage": "COMPLETE",
            "missing_fields": [],
            "confidence_score": situation.confidence,
        }

        # Hash and versioning. `status` is deliberately excluded: it's
        # workflow metadata that this very request path mutates as a side
        # effect (mark_action_recommended flips DETECTED -> ACTION_RECOMMENDED
        # right after a decision/investigation is generated), so including it
        # would change the hash out from under the cache entry just written
        # during seeding, turning every situation's first page view into a
        # guaranteed cache miss and a fresh, slow LLM call.
        situation_data_for_hash = {k: v for k, v in situation_data.items() if k != "status"}
        payload_for_hashing = {
            "sit": situation_data_for_hash,
            "state": current_state,
            "hist": historical_context,
        }
        raw_json = json.dumps(payload_for_hashing, sort_keys=True)
        evidence_hash = hashlib.sha256(raw_json.encode("utf-8")).hexdigest()[:16]

        return EvidencePacket(
            situation=situation_data,
            shift_context=shift_context,
            current_state=current_state,
            historical_context=historical_context,
            alert_context=alert_context,
            root_cause_evidence=root_cause_evidence,
            workforce_impact=workforce_impact,
            future_risk=future_risk,
            recommendation_context=recommendation_context,
            data_confidence=data_confidence,
            context_version="v1.0",
            last_updated_at=datetime.utcnow(),
            evidence_hash=evidence_hash,
        )
