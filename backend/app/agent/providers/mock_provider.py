from __future__ import annotations

import structlog
import json
from typing import Any

from app.domain.interfaces import LLMProvider

logger = structlog.get_logger(__name__)

class MockProvider(LLMProvider):
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        logger.info("Mock LLM generate called")
        
        if "Provide your analysis as a structured JSON" in prompt or "Return JSON only." in (system_prompt or ""):
            return json.dumps({
                "summary": "Mock summary of the situation based on evidence.",
                "why_it_matters": "This impacts employees and delays trips.",
                "historical_comparison": "This is higher than the historical baseline.",
                "contributing_factors": [{"factor": "Late Start", "evidence_type": "OBSERVED_FACT"}],
                "recommended_action": "NOTIFY_EMPLOYEES",
                "alternative_actions": [],
                "confidence": "HIGH",
                "data_quality_notes": "All data looks valid."
            })
            
        if "Explain this situation" in prompt:
            return "This is a mocked explanation of the situation. It affects several employees and requires immediate attention."

        if "Respond with raw JSON only" in prompt and '"needs_data"' in prompt:
            return json.dumps({
                "needs_data": True,
                "sql": "SELECT business_unit, office, COUNT(*) AS delayed_trips FROM analytics.v_trip WHERE trip_date = '2026-07-15' AND is_delayed GROUP BY 1, 2 ORDER BY delayed_trips DESC LIMIT 10",
                "reasoning": "The question asks for specific delay figures, which requires querying trip data.",
            })

        if "Query Results (JSON rows" in prompt:
            return "Mock answer: based on the query results, a handful of offices account for most of today's delays. Review the rows above for exact counts."

        return "This is a mock LLM response."

    async def generate_with_tools(
        self,
        prompt: str,
        tools: list[dict[str, Any]],
        system_prompt: str | None = None,
    ) -> dict[str, Any]:
        logger.info("Mock LLM generate_with_tools called")
        return {
            "content": "Mock response with tools.",
            "tool_calls": []
        }
