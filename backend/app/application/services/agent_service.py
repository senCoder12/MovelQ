from __future__ import annotations

import json
from typing import Any, Dict, Optional

import structlog

from app.agent.prompts.templates import (
    ASK_MOVE_PROMPT,
    SITUATION_INVESTIGATION_PROMPT,
    SYSTEM_PROMPT,
)
from app.agent.providers.mock_provider import MockProvider
from app.application.services.evidence_service import EvidenceService
from app.config import get_settings
from app.domain.entities import Situation
from app.domain.interfaces import LLMProvider, SituationRepository

logger = structlog.get_logger(__name__)


class AgentService:
    """Agentic reasoning engine.

    Uses an LLM selectively over compact EvidencePackets.
    Always provides deterministic template fallbacks if LLM is unavailable.
    """

    def __init__(
        self,
        evidence_service: EvidenceService,
        situation_repository: SituationRepository,
        llm_provider: Optional[LLMProvider] = None,
    ):
        self.evidence_service = evidence_service
        self.situation_repository = situation_repository
        self.settings = get_settings()

        # Wire LLM provider: use OpenAI if key configured, otherwise MockProvider
        if llm_provider is not None:
            self.llm_provider = llm_provider
        elif self.settings.llm_api_key:
            try:
                from app.agent.providers.openai_provider import OpenAIProvider
                self.llm_provider = OpenAIProvider()
            except Exception:
                self.llm_provider = MockProvider()
        else:
            self.llm_provider = MockProvider()

        self._llm_cache: Dict[str, Dict[str, Any]] = {}

    async def investigate_situation(self, situation_id: str) -> Dict[str, Any]:
        """Investigate a situation using selective LLM reasoning over structured evidence."""
        logger.info("agent.investigate", situation_id=situation_id)
        situation = await self.situation_repository.get_situation(situation_id)
        if not situation:
            return {"error": "Situation not found"}

        # 1. Build compact EvidencePacket (deterministic, NO PII)
        packet = await self.evidence_service.build_evidence_packet(situation)
        cache_key = packet.evidence_hash

        # 2. Check result cache
        if cache_key in self._llm_cache:
            logger.info("agent.cache_hit", cache_key=cache_key)
            return self._llm_cache[cache_key]

        # 3. Format prompt
        evidence_json = json.dumps(packet.model_dump(), indent=2, default=str)
        prompt = SITUATION_INVESTIGATION_PROMPT.format(evidence_json=evidence_json)

        # 4. Invoke LLM with fallback
        try:
            raw_response = await self.llm_provider.generate(
                prompt=prompt,
                system_prompt=SYSTEM_PROMPT,
                temperature=self.settings.llm_temperature,
                max_tokens=self.settings.llm_max_tokens,
            )

            # Clean JSON if markdown enclosed
            clean_text = raw_response.strip()
            if clean_text.startswith("```json"):
                clean_text = clean_text[7:]
            if clean_text.endswith("```"):
                clean_text = clean_text[:-3]

            parsed = json.loads(clean_text)
            self._llm_cache[cache_key] = parsed
            return parsed

        except Exception as e:
            logger.warning("agent.llm_fallback_triggered", error=str(e))
            # Level 2 deterministic template explanation (INVARIANT 15)
            fallback = self._generate_template_investigation(situation)
            self._llm_cache[cache_key] = fallback
            return fallback

    def _generate_template_investigation(self, situation: Situation) -> Dict[str, Any]:
        emp_cnt = situation.impact.affected_employees
        delay_min = situation.impact.delay_minutes_total
        office = situation.office or "Oakmont"
        shift = situation.shift or "03:00"

        summary = (
            f"A {situation.situation_type.value} situation was identified at {office} for the {shift} shift. "
            f"It currently affects {emp_cnt} employee(s) with an aggregate delay of {delay_min} minutes."
        )

        why_it_matters = (
            f"Employees on this route are at risk of arriving past work commencement. "
            f"The current shift readiness is negatively impacted by {situation.impact.readiness_delta_pp or 0:+.1f} percentage points."
        )

        hist = situation.impact.historical_delay_p95 or 8.0
        historical_comparison = (
            f"Current arrival lateness is elevated compared to historical reference p90 of {hist:.0f}m."
        )

        factors = [
            {"factor": "Transit disruption / delay accumulation", "evidence_type": "OBSERVED_FACT"},
            {"factor": "Rostered shift window constraint", "evidence_type": "HISTORICAL_EVIDENCE"},
        ]

        rec_action = situation.recommended_actions[0] if situation.recommended_actions else "NOTIFY_EMPLOYEES"

        return {
            "summary": summary,
            "why_it_matters": why_it_matters,
            "historical_comparison": historical_comparison,
            "contributing_factors": factors,
            "recommended_action": rec_action,
            "alternative_actions": situation.recommended_actions[1:],
            "confidence": "HIGH",
            "data_quality_notes": "Computed deterministically from operational facts and validated baseline profiles.",
            "mode": "deterministic_template",
        }

    async def ask_move(self, question: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Ask Move conversational interface."""
        logger.info("agent.ask_move", question=question)

        # Retrieve active situations as context
        active_sits = await self.situation_repository.get_situations(limit=5)
        evidence = {
            "active_situations_count": len(active_sits),
            "top_situations": [
                {
                    "id": s.situation_id,
                    "type": s.situation_type.value,
                    "priority": s.priority.value,
                    "impact": s.impact.model_dump(),
                }
                for s in active_sits
            ],
            "client_context": context,
        }

        prompt = ASK_MOVE_PROMPT.format(
            evidence_json=json.dumps(evidence, indent=2, default=str),
            question=question,
        )

        try:
            answer = await self.llm_provider.generate(
                prompt=prompt,
                system_prompt=SYSTEM_PROMPT,
                temperature=self.settings.llm_temperature,
            )
            return {
                "answer": answer,
                "evidence": evidence,
                "confidence": "HIGH",
            }
        except Exception as e:
            logger.warning("agent.ask_move_fallback", error=str(e))
            return {
                "answer": (
                    f"Based on current telemetry, there are {len(active_sits)} active situation(s) "
                    "requiring operational attention. You can inspect affected employee counts and compare "
                    "remedial interventions in the Situations Command Center."
                ),
                "evidence": evidence,
                "confidence": "MEDIUM",
                "mode": "deterministic_fallback",
            }
