"""Live LLM provider adapter supporting Local 2B models (Ollama/LMStudio), Gemini, and OpenAI APIs."""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional
import httpx

from core.actions.domain import Domain
from core.contracts import FactSchema, TaskProposalSchema
from core.logger import get_logger
from interpretation.llm.base import BaseLLMProvider
from interpretation.llm.mock import MockLLMProvider

logger = get_logger("live_llm")

SYSTEM_FORMALIZER_PROMPT = """You are a robotic task formalizer for the RE-PLAN-V neurosymbolic system.
Your job is to convert natural language instructions into a formal TaskProposal JSON schema for a blocks world environment.

Available Predicates:
- on(top, bottom)
- on_table(block)
- clear(block)
- holding(block)
- handempty()

Respond ONLY with valid JSON conforming to this structure:
{
  "task_id": "task_formalized",
  "raw_prompt": "<original user prompt>",
  "entities": { "<entity_name>": "block" },
  "initial_facts": [
    { "predicate": "on_table", "arguments": ["block_name"] },
    { "predicate": "clear", "arguments": ["block_name"] },
    { "predicate": "handempty", "arguments": [] }
  ],
  "goal_facts": [
    { "predicate": "on", "arguments": ["block_a", "block_b"] }
  ],
  "negative_constraints": [
    { "predicate": "holding", "arguments": ["fragile_object"] }
  ],
  "invariants": [],
  "confidence": 0.95
}
"""


class LiveLLMProvider(BaseLLMProvider):
    """Integrates with local 2B models (Ollama/LM Studio) or cloud LLM endpoints (Gemini/OpenAI)."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        provider: str = "auto",
        model: Optional[str] = None,
        endpoint: Optional[str] = None,
        fallback_provider: Optional[BaseLLMProvider] = None,
    ) -> None:
        self.provider = provider
        self.model = model or "gemma2:2b"
        self.endpoint = endpoint or os.environ.get("LOCAL_LLM_URL", "http://localhost:11434/v1")
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("OPENAI_API_KEY")
        self.fallback = fallback_provider or MockLLMProvider()

    def interpret(self, prompt: str, domain: Domain) -> TaskProposalSchema:
        # Check if local Ollama or live API is explicitly requested or available
        if self.provider == "mock":
            return self.fallback.interpret(prompt, domain)

        # Try Local 2B Model (Ollama / OpenAI-compatible endpoint)
        if self.provider in ("ollama", "local", "auto"):
            try:
                proposal = self._call_openai_compatible(
                    prompt=prompt,
                    endpoint=f"{self.endpoint.rstrip('/')}/chat/completions",
                    model=self.model,
                    api_key="ollama",
                )
                if proposal:
                    return proposal
            except Exception as e:
                logger.debug(f"Local 2B LLM endpoint not available ({e}); checking cloud or fallback.")

        # Try Google Gemini API if GEMINI_API_KEY is available
        gemini_key = self.api_key or os.environ.get("GEMINI_API_KEY")
        if (self.provider in ("gemini", "auto")) and gemini_key:
            try:
                proposal = self._call_gemini_api(prompt=prompt, api_key=gemini_key)
                if proposal:
                    return proposal
            except Exception as e:
                logger.warning(f"Gemini API invocation failed ({e}); falling back.")

        # Try OpenAI API if OPENAI_API_KEY is available
        openai_key = os.environ.get("OPENAI_API_KEY")
        if (self.provider in ("openai", "auto")) and openai_key:
            try:
                proposal = self._call_openai_compatible(
                    prompt=prompt,
                    endpoint="https://api.openai.com/v1/chat/completions",
                    model="gpt-4o-mini",
                    api_key=openai_key,
                )
                if proposal:
                    return proposal
            except Exception as e:
                logger.warning(f"OpenAI API invocation failed ({e}); falling back.")

        # Deterministic zero-API fallback
        return self.fallback.interpret(prompt, domain)

    def _call_openai_compatible(
        self, prompt: str, endpoint: str, model: str, api_key: str
    ) -> Optional[TaskProposalSchema]:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_FORMALIZER_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.0,
            "response_format": {"type": "json_object"},
        }
        with httpx.Client(timeout=5.0) as client:
            resp = client.post(endpoint, json=payload, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                return self._parse_json_to_schema(content, prompt)
        return None

    def _call_gemini_api(self, prompt: str, api_key: str) -> Optional[TaskProposalSchema]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": SYSTEM_FORMALIZER_PROMPT},
                        {"text": f"Instruction: {prompt}"},
                    ]
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.0,
            },
        }
        with httpx.Client(timeout=8.0) as client:
            resp = client.post(url, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                return self._parse_json_to_schema(text, prompt)
        return None

    def _parse_json_to_schema(self, raw_json_str: str, prompt: str) -> TaskProposalSchema:
        clean_json = raw_json_str.strip()
        match = re.search(r"(\{.*\})", clean_json, re.DOTALL)
        if match:
            clean_json = match.group(1)
        parsed = json.loads(clean_json)

        entities = parsed.get("entities", {})
        initial_facts = [
            FactSchema(predicate=f["predicate"], arguments=tuple(f["arguments"]))
            for f in parsed.get("initial_facts", [])
        ]
        goal_facts = [
            FactSchema(predicate=f["predicate"], arguments=tuple(f["arguments"]))
            for f in parsed.get("goal_facts", [])
        ]
        negative_constraints = [
            FactSchema(predicate=f["predicate"], arguments=tuple(f["arguments"]))
            for f in parsed.get("negative_constraints", [])
        ]
        invariants = [
            FactSchema(predicate=f["predicate"], arguments=tuple(f["arguments"]))
            for f in parsed.get("invariants", [])
        ]

        return TaskProposalSchema(
            task_id=parsed.get("task_id", "llm_formalized"),
            raw_prompt=prompt,
            entities=entities,
            initial_facts=initial_facts,
            goal_facts=goal_facts,
            negative_constraints=negative_constraints,
            invariants=invariants,
            confidence=float(parsed.get("confidence", 0.9)),
        )

