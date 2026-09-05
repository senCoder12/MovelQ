from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, Optional

import structlog

from app.agent.prompts.templates import (
    ANALYTICS_SCHEMA_DESCRIPTION,
    ANSWER_WITH_DATA_PROMPT,
    ASK_MOVE_PROMPT,
    SITUATION_INVESTIGATION_PROMPT,
    SQL_ROUTER_PROMPT,
    SYSTEM_PROMPT,
)
from app.agent.sql_guard import enforce_limit, is_safe_select
from app.application.services.evidence_service import EvidenceService
from app.config import get_settings
from app.domain.entities import Situation
from app.domain.interfaces import LLMProvider, SituationRepository

_LLM_TIMEOUT_SECONDS = 25

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

        # Wire LLM provider based on LLM_MODEL/LLM_API_KEY, otherwise MockProvider
        if llm_provider is not None:
            self.llm_provider = llm_provider
        else:
            from app.agent.providers.factory import build_llm_provider
            self.llm_provider = build_llm_provider()

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

            # strict=False: Gemini/GPT JSON responses sometimes contain raw
            # newlines inside string values, which the strict JSON grammar rejects.
            parsed = json.loads(clean_text, strict=False)
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

    async def _generate(self, prompt: str, **kwargs: Any) -> str:
        """LLM call with a hard timeout so one slow request can never hang the app."""
        return await asyncio.wait_for(
            self.llm_provider.generate(prompt=prompt, **kwargs),
            timeout=_LLM_TIMEOUT_SECONDS,
        )

    @staticmethod
    def _parse_json_response(raw: str) -> Dict[str, Any]:
        clean_text = raw.strip()
        if clean_text.startswith("```json"):
            clean_text = clean_text[7:]
        elif clean_text.startswith("```"):
            clean_text = clean_text[3:]
        if clean_text.endswith("```"):
            clean_text = clean_text[:-3]
        return json.loads(clean_text.strip(), strict=False)

    async def _route_question(self, question: str) -> Dict[str, Any]:
        """Ask the LLM whether this question needs a database query, and if so, what SQL."""
        prompt = SQL_ROUTER_PROMPT.format(
            schema=ANALYTICS_SCHEMA_DESCRIPTION,
            question=question,
        )
        raw = await self._generate(prompt, system_prompt=SYSTEM_PROMPT, temperature=0.0)
        return self._parse_json_response(raw)

    async def ask_move(self, question: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Ask Move conversational interface: question -> LLM decides if data is needed ->
        text-to-SQL against the analytics schema -> LLM formats the result -> answer.
        """
        logger.info("agent.ask_move", question=question)

        route: Dict[str, Any] = {}
        try:
            route = await self._route_question(question)
        except Exception as e:
            logger.warning("agent.sql_routing_failed", error=str(e))

        sql = route.get("sql")
        if route.get("needs_data") and sql:
            if not is_safe_select(sql):
                logger.warning("agent.unsafe_sql_blocked", sql=sql)
            else:
                try:
                    from app.infrastructure.database import fetch_rows

                    safe_sql = enforce_limit(sql)
                    rows = await asyncio.wait_for(fetch_rows(safe_sql), timeout=12)
                    row_dicts = [dict(r) for r in rows]

                    answer_prompt = ANSWER_WITH_DATA_PROMPT.format(
                        question=question,
                        sql=safe_sql,
                        row_count=len(row_dicts),
                        rows_json=json.dumps(row_dicts[:20], indent=2, default=str),
                    )
                    answer = await self._generate(
                        answer_prompt,
                        system_prompt=SYSTEM_PROMPT,
                        temperature=self.settings.llm_temperature,
                    )
                    return {
                        "answer": answer,
                        "evidence": {
                            "sql": safe_sql,
                            "row_count": len(row_dicts),
                            "rows": row_dicts[:20],
                        },
                        "confidence": "HIGH",
                        "mode": "text_to_sql",
                    }
                except Exception as e:
                    logger.warning("agent.sql_execution_failed", error=str(e), sql=sql)
                    # Falls through to the conversational path below.

        # No data needed, routing failed, or the SQL was rejected/errored --
        # answer conversationally from active-situation context instead.
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
            answer = await self._generate(
                prompt,
                system_prompt=SYSTEM_PROMPT,
                temperature=self.settings.llm_temperature,
            )
            return {
                "answer": answer,
                "evidence": evidence,
                "confidence": "MEDIUM" if route else "HIGH",
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
