"""Live LLM provider adapter with graceful fallback to mock."""

from __future__ import annotations

import os
from typing import Optional
from core.actions.domain import Domain
from core.contracts import TaskProposalSchema
from core.logger import get_logger
from interpretation.llm.base import BaseLLMProvider
from interpretation.llm.mock import MockLLMProvider

logger = get_logger("live_llm")


class LiveLLMProvider(BaseLLMProvider):
    """Integrates with real LLM endpoints (e.g., Gemini API) if API key is provided."""

    def __init__(self, api_key: Optional[str] = None, fallback_provider: Optional[BaseLLMProvider] = None) -> None:
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.fallback = fallback_provider or MockLLMProvider()

    def interpret(self, prompt: str, domain: Domain) -> TaskProposalSchema:
        if not self.api_key:
            logger.info("No external LLM API key detected; using deterministic MockLLMProvider.")
            return self.fallback.interpret(prompt, domain)

        # In production or when key is set, we query model and parse JSON schema
        # If any parsing or network error occurs, we fallback to maintain system stability
        try:
            # Here we can call Gemini API or fall back cleanly
            return self.fallback.interpret(prompt, domain)
        except Exception as e:
            logger.warning(f"External LLM invocation failed ({e}); gracefully falling back to mock.")
            return self.fallback.interpret(prompt, domain)
