from __future__ import annotations

import time
from typing import Any, Dict, Tuple, Optional
from app.config import get_settings

class LLMCache:
    def __init__(self):
        self.settings = get_settings()
        self.cache: Dict[Tuple[str, str, str], dict] = {}
        self.hits = 0
        self.misses = 0

    def get(self, situation_id: str, evidence_hash: str, prompt_version: str) -> Optional[dict]:
        key = (situation_id, evidence_hash, prompt_version)
        if key in self.cache:
            entry = self.cache[key]
            if time.time() - entry["timestamp"] < self.settings.llm_cache_ttl_seconds:
                self.hits += 1
                return entry["response"]
            else:
                del self.cache[key]
        self.misses += 1
        return None

    def set(self, situation_id: str, evidence_hash: str, prompt_version: str, response: dict) -> None:
        key = (situation_id, evidence_hash, prompt_version)
        self.cache[key] = {
            "response": response,
            "timestamp": time.time()
        }
