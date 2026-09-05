from __future__ import annotations

import structlog

from app.config import get_settings
from app.domain.interfaces import LLMProvider

logger = structlog.get_logger(__name__)


def build_llm_provider() -> LLMProvider:
    """Select and construct the LLM provider configured via LLM_MODEL/LLM_API_KEY.

    Picks Gemini or OpenAI based on the configured model name. Falls back to
    MockProvider if no API key is set or the provider fails to initialize.
    """
    settings = get_settings()
    from app.agent.providers.mock_provider import MockProvider

    if not settings.llm_api_key:
        return MockProvider()

    model = settings.llm_model.lower()
    try:
        if "gemini" in model:
            from app.agent.providers.gemini_provider import GeminiProvider
            return GeminiProvider()
        from app.agent.providers.openai_provider import OpenAIProvider
        return OpenAIProvider()
    except Exception as e:
        logger.warning("llm.provider_init_failed", error=str(e), model=model)
        return MockProvider()
