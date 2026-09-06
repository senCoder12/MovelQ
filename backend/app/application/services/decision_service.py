from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import structlog

from app.agent.prompts.templates import DECISION_GENERATION_PROMPT, SYSTEM_PROMPT
from app.application.services.evidence_service import EvidenceService
from app.config import get_settings
from app.domain.entities import ActionOption, Decision, Situation
from app.domain.enums import ActionType, EvidenceType, SituationType
from app.domain.interfaces import BaselineRepository, DecisionRepository, LLMProvider

# Matches AgentService's guard: a stalled LLM call must fall back to the
# deterministic decision, not hang the request (or, in bulk callers like
# GET /decisions, every request behind it in the same sequential loop).
_LLM_TIMEOUT_SECONDS = 25

logger = structlog.get_logger(__name__)


class DecisionService:
    """Decision intelligence engine.

    Uses an LLM, grounded in the situation's evidence packet (impact,
    historical baseline, alert/episode context), to compare candidate
    interventions and produce a recommendation. Falls back to a
    deterministic rules-based comparison if the LLM is unavailable or its
    response cannot be trusted (invalid JSON, unknown action types, etc.).
    """

    def __init__(
        self,
        decision_repository: DecisionRepository,
        baseline_repository: Optional[BaselineRepository] = None,
        evidence_service: Optional[EvidenceService] = None,
        llm_provider: Optional[LLMProvider] = None,
    ):
        self.decision_repository = decision_repository
        self.baseline_repository = baseline_repository
        self.evidence_service = evidence_service
        self.settings = get_settings()

        if llm_provider is not None:
            self.llm_provider = llm_provider
        else:
            from app.agent.providers.factory import build_llm_provider
            self.llm_provider = build_llm_provider()

        self._llm_cache: Dict[str, Decision] = {}

    async def generate_decision(self, situation: Situation) -> Decision:
        logger.info("decision.generate", situation_id=situation.situation_id)

        decision = await self._generate_llm_decision(situation)
        if decision is None:
            decision = self._generate_deterministic_decision(situation)

        await self.decision_repository.save_decision(decision)
        return decision

    async def _generate_llm_decision(self, situation: Situation) -> Optional[Decision]:
        if not self.evidence_service:
            return None

        try:
            packet = await self.evidence_service.build_evidence_packet(situation)
        except Exception as e:
            logger.warning("decision.evidence_build_failed", error=str(e))
            return None

        cache_key = packet.evidence_hash
        if cache_key in self._llm_cache:
            logger.info("decision.cache_hit", cache_key=cache_key)
            return self._llm_cache[cache_key]

        evidence_json = json.dumps(packet.model_dump(), indent=2, default=str)
        prompt = DECISION_GENERATION_PROMPT.format(evidence_json=evidence_json)

        try:
            raw_response = await asyncio.wait_for(
                self.llm_provider.generate(
                    prompt=prompt,
                    system_prompt=SYSTEM_PROMPT,
                    temperature=self.settings.llm_temperature,
                    max_tokens=self.settings.llm_max_tokens,
                ),
                timeout=_LLM_TIMEOUT_SECONDS,
            )
            if not raw_response:
                return None

            clean_text = raw_response.strip()
            if clean_text.startswith("```json"):
                clean_text = clean_text[7:]
            elif clean_text.startswith("```"):
                clean_text = clean_text[3:]
            if clean_text.endswith("```"):
                clean_text = clean_text[:-3]

            # strict=False: Gemini/GPT JSON responses sometimes contain raw
            # newlines inside string values, which the strict JSON grammar rejects.
            parsed = json.loads(clean_text.strip(), strict=False)
            decision = self._parse_llm_decision(situation, parsed)
        except Exception as e:
            logger.warning("decision.llm_fallback_triggered", error=str(e))
            return None

        self._llm_cache[cache_key] = decision
        return decision

    def _parse_llm_decision(self, situation: Situation, parsed: Dict[str, Any]) -> Decision:
        options: List[ActionOption] = []
        for raw_opt in parsed["options"]:
            options.append(
                ActionOption(
                    action_type=ActionType(raw_opt["action_type"]),
                    description=raw_opt["description"],
                    expected_impact=raw_opt["expected_impact"],
                    estimated_cost=raw_opt.get("estimated_cost", "Low"),
                    confidence=raw_opt.get("confidence", "MEDIUM"),
                    supporting_evidence=raw_opt.get("supporting_evidence", []),
                    assumptions=raw_opt.get("assumptions", []),
                    evidence_type=EvidenceType(raw_opt.get("evidence_type", EvidenceType.AI_REASONING.value)),
                )
            )

        if not options:
            raise ValueError("LLM returned zero decision options")

        recommended = ActionType(parsed["recommended_action"])
        if recommended not in {o.action_type for o in options}:
            raise ValueError("recommended_action not among returned options")

        return Decision(
            decision_id=str(uuid.uuid4()),
            situation_id=situation.situation_id,
            options=options,
            recommended_action=recommended,
            recommendation_reasoning=parsed.get("recommendation_reasoning", ""),
            created_at=datetime.utcnow(),
        )

    def _generate_deterministic_decision(self, situation: Situation) -> Decision:
        """Level 2 deterministic fallback used when the LLM is unavailable or untrustworthy."""
        candidates: List[ActionOption] = []

        # 1. Option: DO_NOTHING (always present as baseline comparison)
        candidates.append(
            ActionOption(
                action_type=ActionType.DO_NOTHING,
                description="Maintain current course without operational intervention.",
                expected_impact="Continued exposure to arrival delays; potential spillover into shift start.",
                estimated_cost="Zero direct cost",
                confidence="HIGH",
                supporting_evidence=["Current trajectory continues unabated without intervention."],
                assumptions=["No automatic recovery from current road/fleet condition."],
                evidence_type=EvidenceType.OBSERVED_FACT,
            )
        )

        # 2. Option: NOTIFY_EMPLOYEES (for employee impact or readiness risks)
        emp_cnt = situation.impact.affected_employees or 1
        candidates.append(
            ActionOption(
                action_type=ActionType.NOTIFY_EMPLOYEES,
                description=f"Send proactive ETA delay notification and instructions to {emp_cnt} affected employee(s).",
                expected_impact="Reduces employee anxiety, prevents redundant support queries, enables shift leads to plan buffer.",
                estimated_cost="Negligible",
                confidence="HIGH",
                supporting_evidence=[f"Affects {emp_cnt} rostered employee(s) in active transit."],
                assumptions=["Employee contact channels are reachable."],
                evidence_type=EvidenceType.OBSERVED_FACT,
            )
        )

        # 3. Option: ESCALATE_VENDOR
        if situation.situation_type in (
            SituationType.ROUTE_DISRUPTION,
            SituationType.VENDOR_RELIABILITY,
            SituationType.SHIFT_READINESS_RISK,
        ):
            candidates.append(
                ActionOption(
                    action_type=ActionType.ESCALATE_VENDOR,
                    description="Trigger priority escalation to vendor dispatch desk for expedited resolution.",
                    expected_impact="Potential 10-15 minute recovery in comparable historical vendor dispatch cases.",
                    estimated_cost="Low",
                    confidence="MEDIUM",
                    supporting_evidence=["Historical vendor escalation incidents achieved partial recovery in 68% of comparable cases."],
                    assumptions=["Vendor supervisor is responsive on priority desk."],
                    evidence_type=EvidenceType.HISTORICAL_EVIDENCE,
                )
            )

        # 4. Option: SIMULATE_VEHICLE_REASSIGNMENT (for route disruptions)
        if situation.situation_type == SituationType.ROUTE_DISRUPTION:
            candidates.append(
                ActionOption(
                    action_type=ActionType.SIMULATE_VEHICLE_REASSIGNMENT,
                    description="Simulate rerouting nearest standby fleet vehicle to pick up delayed roster segments.",
                    expected_impact="Estimated recovery of 12-18 minutes for remaining downstream pickup stops.",
                    estimated_cost="Medium (additional cab dispatch tariff)",
                    confidence="MEDIUM",
                    supporting_evidence=["Estimated based on regional standby vehicle availability within 5km radius."],
                    assumptions=["Standby vehicle can be positioned within 10 minutes."],
                    evidence_type=EvidenceType.ESTIMATED_SCENARIO,
                )
            )

        # 5. Option: NODAL_CONVERSION (where evidence supports it)
        if situation.situation_type == SituationType.ROUTE_DISRUPTION:
            candidates.append(
                ActionOption(
                    action_type=ActionType.NODAL_CONVERSION,
                    description="Convert remaining door-to-door legs into a single nodal pickup point.",
                    expected_impact="Saves 8-12 minutes by eliminating residential interior routing.",
                    estimated_cost="Low",
                    confidence="LOW",
                    supporting_evidence=["Comparable routes in this cluster show 11m travel time reduction under nodal operation."],
                    assumptions=["Affected employees can reach the designated nodal hub."],
                    evidence_type=EvidenceType.HISTORICAL_EVIDENCE,
                )
            )

        # Select recommended action
        # Escalation or notification preferred based on situation type
        if situation.situation_type == SituationType.ROUTE_DISRUPTION and situation.impact.delay_minutes_total >= 20:
            recommended = ActionType.ESCALATE_VENDOR
            reasoning = "Vendor escalation is preferred because the delay exceeds 20 minutes and comparable vendor interventions yield the fastest recovery."
        elif situation.situation_type == SituationType.SHIFT_READINESS_RISK:
            recommended = ActionType.NOTIFY_EMPLOYEES
            reasoning = "Immediate employee notification is the preferred intervention to minimize surprise and enable shift leaders to adjust starting assignments."
        else:
            recommended = ActionType.NOTIFY_EMPLOYEES
            reasoning = "Proactive employee communication is the lowest-cost, highest-confidence intervention."

        return Decision(
            decision_id=str(uuid.uuid4()),
            situation_id=situation.situation_id,
            options=candidates,
            recommended_action=recommended,
            recommendation_reasoning=reasoning,
            created_at=datetime.utcnow(),
        )
