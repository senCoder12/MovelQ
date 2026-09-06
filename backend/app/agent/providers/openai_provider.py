from __future__ import annotations

import structlog
from typing import Any, Dict, List, Optional
import openai
from pydantic import BaseModel
from openai import AsyncOpenAI

from app.domain.interfaces import LLMProvider
from app.config import get_settings

logger = structlog.get_logger(__name__)

class OpenAIProvider(LLMProvider):
    def __init__(self):
        self.settings = get_settings()
        self.client = AsyncOpenAI(api_key=self.settings.llm_api_key)
        self.model = self.settings.llm_model
        self.calls_count = 0

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        temp = temperature if temperature is not None else self.settings.llm_temperature
        tokens = max_tokens if max_tokens is not None else self.settings.llm_max_tokens

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temp,
                max_tokens=tokens,
            )
            self.calls_count += 1
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error("OpenAI generate failed", error=str(e))
            return ""

    async def generate_with_tools(
        self,
        prompt: str,
        tools: list[dict[str, Any]],
        system_prompt: str | None = None,
    ) -> dict[str, Any]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools,
                temperature=0.3,
            )
            self.calls_count += 1
            
            message = response.choices[0].message
            return {
                "content": message.content or "",
                "tool_calls": [
                    {
                        "id": tool_call.id,
                        "function": {
                            "name": tool_call.function.name,
                            "arguments": tool_call.function.arguments,
                        },
                        "type": tool_call.type,
                    }
                    for tool_call in (message.tool_calls or [])
                ],
            }
        except Exception as e:
            logger.error("OpenAI generate_with_tools failed", error=str(e))
            return {"content": "", "tool_calls": []}
