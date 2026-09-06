from __future__ import annotations

import structlog
from typing import Any

from google import genai
from google.genai import types

from app.domain.interfaces import LLMProvider
from app.config import get_settings

logger = structlog.get_logger(__name__)


class GeminiProvider(LLMProvider):
    """Google Gemini-backed LLM provider."""

    def __init__(self):
        self.settings = get_settings()
        self.client = genai.Client(api_key=self.settings.llm_api_key)
        self.model = self.settings.llm_model
        self.calls_count = 0

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        config = types.GenerateContentConfig(
            temperature=temperature if temperature is not None else self.settings.llm_temperature,
            max_output_tokens=max_tokens if max_tokens is not None else self.settings.llm_max_tokens,
            system_instruction=system_prompt or None,
        )

        try:
            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=prompt,
                config=config,
            )
            self.calls_count += 1
            return response.text or ""
        except Exception as e:
            logger.error("Gemini generate failed", error=str(e))
            return ""

    async def generate_with_tools(
        self,
        prompt: str,
        tools: list[dict[str, Any]],
        system_prompt: str | None = None,
    ) -> dict[str, Any]:
        text = await self.generate(prompt, system_prompt=system_prompt)
        return {"content": text, "tool_calls": []}
