"""Base interface for LLM natural language interpretation providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional
from core.actions.domain import Domain
from core.contracts import TaskProposalSchema


class BaseLLMProvider(ABC):
    """Abstract provider for interpreting natural language tasks into structured proposals."""

    @abstractmethod
    def interpret(self, prompt: str, domain: Domain) -> TaskProposalSchema:
        pass
