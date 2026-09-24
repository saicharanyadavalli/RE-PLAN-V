"""Live LLM provider adapter supporting Local 2B models (LM Studio / Ollama), Gemini, and OpenAI APIs."""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional, Set, Tuple
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
  "entities": { "red_box": "block", "blue_box": "block", "glass": "block" },
  "initial_facts": [
    { "predicate": "on_table", "arguments": ["red_box"] },
    { "predicate": "clear", "arguments": ["red_box"] },
    { "predicate": "on_table", "arguments": ["blue_box"] },
    { "predicate": "clear", "arguments": ["blue_box"] },
    { "predicate": "on_table", "arguments": ["glass"] },
    { "predicate": "clear", "arguments": ["glass"] },
    { "predicate": "handempty", "arguments": [] }
  ],
  "goal_facts": [
    { "predicate": "on", "arguments": ["red_box", "blue_box"] }
  ],
  "negative_constraints": [
    { "predicate": "holding", "arguments": ["glass"] }
  ],
  "invariants": [],
  "confidence": 0.95
}
CRITICAL FORMALIZATION RULES:
1. "entities": Keys MUST be unique snake_case names (e.g. "red_box", "blue_box", "glass") and values must be "block".
2. "initial_facts":
   - EVERY entity is initially resting on the table ("on_table") and "clear", UNLESS explicitly stated as stacked (e.g., "red is on green" -> on(red, green), clear(red), on_table(green)).
   - Robot hand is initially empty: {"predicate": "handempty", "arguments": []}.
   - NEVER put {"predicate": "holding", "arguments": ["X"]} in initial_facts unless the user prompt says "the robot is currently holding X".
3. "negative_constraints":
   - For safety instructions like "do not touch/move/hold X", use {"predicate": "holding", "arguments": ["X"]}.
   - Do NOT put "clear" or "on_table" in negative_constraints.
4. "goal_facts":
   - Target configurations such as {"predicate": "on", "arguments": ["top_block", "bottom_block"]}.
   - When prompt says "Pick up A and stack on B", the goal is ONLY {"predicate": "on", "arguments": ["A", "B"]}. Top block is A, bottom block is B. Do NOT include holding(A) in goal_facts.
   - If the prompt specifies circular or simultaneous operations (e.g. "put A on B and B on A simultaneously"), you MUST include BOTH goals in "goal_facts": on(A, B) and on(B, A). Do not drop or simplify either condition.
5. Consistency: All predicate arguments must match the keys in "entities" exactly.
"""


class LiveLLMProvider(BaseLLMProvider):
    """Integrates with local 2B models (LM Studio / Ollama) or cloud LLM endpoints (Gemini / OpenAI)."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        provider: str = "auto",
        model: Optional[str] = None,
        endpoint: Optional[str] = None,
        fallback_provider: Optional[BaseLLMProvider] = None,
    ) -> None:
        # Dynamically reload .env so changes made by user take effect immediately without server restart
        try:
            from dotenv import load_dotenv
            from pathlib import Path
            env_file = Path(__file__).resolve().parent.parent.parent / ".env"
            if env_file.exists():
                load_dotenv(dotenv_path=env_file, override=True)
        except Exception:
            pass

        self.provider = (provider or "auto").lower()
        self.model = model
        self.lm_studio_url = os.environ.get("LM_STUDIO_URL", "http://127.0.0.1:1234").rstrip("/")
        self.endpoint = endpoint or os.environ.get("LOCAL_LLM_URL", "http://localhost:11434/v1")
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("OPENAI_API_KEY")
        self.fallback = fallback_provider or MockLLMProvider()

    def interpret(self, prompt: str, domain: Domain) -> TaskProposalSchema:
        """Interprets a natural language instruction into a formal TaskProposalSchema."""
        # 1. Deterministic zero-API mock requested
        if self.provider == "mock":
            return self.fallback.interpret(prompt, domain)

        # 2. LM Studio Local Model (Native v1 /api/v1/chat or /v1/chat/completions)
        if self.provider in ("lmstudio", "lm_studio", "local_lm", "auto"):
            try:
                proposal = self._call_lm_studio(prompt)
                if proposal:
                    logger.info(f"Successfully formalized prompt via LM Studio: {prompt[:40]}...")
                    return proposal
            except Exception as e:
                logger.debug(f"LM Studio call failed ({e}); evaluating other providers or fallback.")

        # 3. Local Ollama 2B Model
        if self.provider in ("ollama", "local", "auto"):
            try:
                proposal = self._call_openai_compatible(
                    prompt=prompt,
                    endpoint=f"{self.endpoint.rstrip('/')}/chat/completions",
                    model=self.model or "gemma2:2b",
                    api_key="ollama",
                )
                if proposal:
                    logger.info(f"Successfully formalized prompt via Ollama: {prompt[:40]}...")
                    return proposal
            except Exception as e:
                logger.debug(f"Ollama call failed ({e}); checking cloud or fallback.")

        # 4. Google Gemini API (if GEMINI_API_KEY is provided)
        gemini_key = self.api_key or os.environ.get("GEMINI_API_KEY")
        if (self.provider in ("gemini", "auto")) and gemini_key:
            try:
                proposal = self._call_gemini_api(prompt=prompt, api_key=gemini_key)
                if proposal:
                    logger.info(f"Successfully formalized prompt via Gemini API: {prompt[:40]}...")
                    return proposal
            except Exception as e:
                logger.warning(f"Gemini API invocation failed ({e}); falling back.")

        # 5. OpenAI API (if OPENAI_API_KEY is provided)
        openai_key = os.environ.get("OPENAI_API_KEY")
        if (self.provider in ("openai", "auto")) and openai_key:
            try:
                proposal = self._call_openai_compatible(
                    prompt=prompt,
                    endpoint="https://api.openai.com/v1/chat/completions",
                    model=self.model or os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
                    api_key=openai_key,
                )
                if proposal:
                    logger.info(f"Successfully formalized prompt via OpenAI: {prompt[:40]}...")
                    return proposal
            except Exception as e:
                logger.warning(f"OpenAI API invocation failed ({e}); falling back.")

        # 6. Fallback to deterministic zero-API rule-based mock
        logger.info(f"Using deterministic zero-API fallback for prompt: '{prompt}'")
        return self.fallback.interpret(prompt, domain)

    def interpret_with_retry(
        self,
        prompt: str,
        domain: Domain,
        max_retries: int = 3,
        validation_errors: Optional[List[str]] = None,
    ) -> Tuple[TaskProposalSchema, str]:
        """Interprets with retry-on-error feedback. Returns (proposal, provider_name).

        If validation_errors is provided, augments the prompt with error feedback
        so the LLM can self-correct its output.
        """
        effective_prompt = prompt
        if validation_errors:
            error_feedback = "\n".join(f"- {e}" for e in validation_errors)
            effective_prompt = (
                f"{prompt}\n\n"
                f"IMPORTANT CORRECTION: Your previous formalization had these errors:\n"
                f"{error_feedback}\n"
                f"Please fix these issues in your JSON output."
            )

        # Try each provider and track which one succeeded
        if self.provider == "mock":
            return self.fallback.interpret(effective_prompt, domain), "mock"

        # LM Studio
        if self.provider in ("lmstudio", "lm_studio", "local_lm", "auto"):
            try:
                proposal = self._call_lm_studio(effective_prompt)
                if proposal:
                    return proposal, f"lmstudio:{self.model or 'auto'}"
            except Exception as e:
                logger.debug(f"LM Studio retry attempt failed: {e}")

        # Ollama
        if self.provider in ("ollama", "local", "auto"):
            try:
                proposal = self._call_openai_compatible(
                    prompt=effective_prompt,
                    endpoint=f"{self.endpoint.rstrip('/')}/chat/completions",
                    model=self.model or "gemma2:2b",
                    api_key="ollama",
                )
                if proposal:
                    return proposal, f"ollama:{self.model or 'gemma2:2b'}"
            except Exception as e:
                logger.debug(f"Ollama retry attempt failed: {e}")

        # Gemini
        gemini_key = self.api_key or os.environ.get("GEMINI_API_KEY")
        if (self.provider in ("gemini", "auto")) and gemini_key:
            try:
                proposal = self._call_gemini_api(prompt=effective_prompt, api_key=gemini_key)
                if proposal:
                    return proposal, f"gemini:{os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash')}"
            except Exception as e:
                logger.debug(f"Gemini retry attempt failed: {e}")

        # OpenAI
        openai_key = os.environ.get("OPENAI_API_KEY")
        if (self.provider in ("openai", "auto")) and openai_key:
            try:
                proposal = self._call_openai_compatible(
                    prompt=effective_prompt,
                    endpoint="https://api.openai.com/v1/chat/completions",
                    model=self.model or os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
                    api_key=openai_key,
                )
                if proposal:
                    return proposal, f"openai:{self.model or 'gpt-4o-mini'}"
            except Exception as e:
                logger.debug(f"OpenAI retry attempt failed: {e}")

        # Fallback
        return self.fallback.interpret(effective_prompt, domain), "mock_fallback"

    def _call_lm_studio(self, prompt: str) -> Optional[TaskProposalSchema]:
        """Communicates with LM Studio via Native v1 REST API (/api/v1/chat) or OpenAI-compatible endpoint."""
        base_url = self.lm_studio_url
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        # Fast connect-check to verify LM Studio is actively listening on port
        timeout = httpx.Timeout(120.0, connect=5.0)
        with httpx.Client(trust_env=False, timeout=timeout) as client:
            detected_model = self.model
            try:
                # First query LM Studio Native v1 API to check loaded instances
                v1_resp = client.get(f"{base_url}/api/v1/models", headers=headers)
                if v1_resp.status_code == 200:
                    models_list = v1_resp.json().get("models", [])
                    for m in models_list:
                        if m.get("loaded_instances") and not detected_model:
                            detected_model = m.get("key")
                            logger.info(f"Detected loaded LM Studio model: {detected_model}")
                            break
                if not detected_model:
                    # Fallback to OpenAI-compatible /v1/models
                    ping_resp = client.get(f"{base_url}/v1/models", headers=headers)
                    if ping_resp.status_code == 200:
                        m_data = ping_resp.json()
                        data_items = m_data.get("data", [])
                        if data_items and "id" in data_items[0]:
                            detected_model = data_items[0]["id"]
            except (httpx.ConnectTimeout, httpx.ConnectError, Exception) as e:
                logger.debug(f"LM Studio local server not running at {base_url} ({e}); skipping.")
                return None

            # 1. Primary: OpenAI-compatible endpoint with assistant thinking-bypass prefill
            openai_url = f"{base_url}/v1/chat/completions"
            openai_payload = {
                "model": detected_model or "local-model",
                "messages": [
                    {"role": "system", "content": SYSTEM_FORMALIZER_PROMPT},
                    {"role": "user", "content": prompt},
                    {"role": "assistant", "content": "</think>```json\n"},
                ],
                "temperature": 0.0,
                "max_tokens": 512,
            }
            try:
                resp = client.post(openai_url, json=openai_payload, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    msg = data["choices"][0]["message"]
                    content = msg.get("content") or ""
                    # If model returned reasoning_content instead of content
                    if not content and "reasoning_content" in msg:
                        content = msg["reasoning_content"]
                    if content:
                        return self._parse_json_to_schema(content, prompt)
            except Exception as e:
                logger.debug(f"LM Studio /v1/chat/completions failed ({e}); attempting native endpoint.")

            # 2. Fallback: LM Studio Native v1 REST API (/api/v1/chat)
            native_url = f"{base_url}/api/v1/chat"
            native_payload = {
                "model": detected_model,
                "input": prompt,
                "system_prompt": SYSTEM_FORMALIZER_PROMPT,
                "temperature": 0.0,
            }
            try:
                resp = client.post(native_url, json=native_payload, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    content = data.get("content") or (data.get("message") or {}).get("content")
                    if content:
                        return self._parse_json_to_schema(content, prompt)
            except Exception as e:
                logger.debug(f"LM Studio native v1 API failed: {e}")

        return None

    def _call_gemini_api(self, prompt: str, api_key: str) -> Optional[TaskProposalSchema]:
        """Calls official Google Gemini API to formalize natural language into JSON schema."""
        preferred_model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
        candidate_models = [preferred_model]
        for fallback in ["gemini-2.5-flash", "gemini-flash-latest", "gemini-2.5-flash-lite"]:
            if fallback not in candidate_models:
                candidate_models.append(fallback)

        for model_name in candidate_models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
            payload = {
                "contents": [
                    {
                        "parts": [
                            {"text": SYSTEM_FORMALIZER_PROMPT},
                            {"text": f"Task instruction: {prompt}"},
                        ]
                    }
                ],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "temperature": 0.0,
                },
            }
            # Try both trust_env=True and trust_env=False to bypass restrictive Windows local proxies
            for trust in [True, False]:
                try:
                    with httpx.Client(timeout=20.0, trust_env=trust) as client:
                        resp = client.post(url, json=payload)
                        if resp.status_code == 200:
                            data = resp.json()
                            text = data["candidates"][0]["content"]["parts"][0]["text"]
                            return self._parse_json_to_schema(text, prompt)
                        elif resp.status_code == 404:
                            logger.info(f"Gemini model '{model_name}' returned 404; trying fallback.")
                            break
                        else:
                            logger.warning(f"Gemini API returned status {resp.status_code}: {resp.text[:200]}")
                            break
                except Exception as e:
                    logger.debug(f"Gemini API attempt (model={model_name}, trust_env={trust}) failed: {e}")
        return None

    def _call_openai_compatible(
        self, prompt: str, endpoint: str, model: str, api_key: str
    ) -> Optional[TaskProposalSchema]:
        """Calls standard OpenAI-compatible completions API."""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_FORMALIZER_PROMPT},
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": "</think>```json\n"},
            ],
            "temperature": 0.0,
            "max_tokens": 512,
        }
        is_local = "127.0.0.1" in endpoint or "localhost" in endpoint
        with httpx.Client(trust_env=not is_local, timeout=45.0) as client:
            resp = client.post(endpoint, json=payload, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                return self._parse_json_to_schema(content, prompt)
        return None

    def _parse_json_to_schema(self, raw_json_str: str, prompt: str) -> TaskProposalSchema:
        """Parses model output JSON into a strongly typed TaskProposalSchema."""
        clean_json = raw_json_str.strip()
        match = re.search(r"(\{.*\})", clean_json, re.DOTALL)
        if match:
            clean_json = match.group(1)
        parsed = json.loads(clean_json)

        # Normalize entities (handles dict {"a": "block"}, list [{"type": "..", "value": "a"}], or list ["a", "b"])
        # Normalize entities (handles dict {"a": "block"}, list [{"type": "..", "value": "a"}], or list ["a", "b"])
        entities_raw = parsed.get("entities", {})
        entities: Dict[str, str] = {}
        if isinstance(entities_raw, dict):
            for k, v in entities_raw.items():
                norm_k = str(k).strip().replace(" ", "_")
                norm_v = str(v).strip().replace(" ", "_")
                if norm_v in ("block", "object", "item"):
                    entities[norm_k] = norm_v
                else:
                    # e.g. {"red box": "red_box"}
                    entities[norm_k] = "block"
                    entities[norm_v] = "block"
        elif isinstance(entities_raw, list):
            for item in entities_raw:
                if isinstance(item, dict):
                    name = str(item.get("value") or item.get("name") or str(item)).strip().replace(" ", "_")
                    etype = item.get("type", "block")
                    entities[name] = etype
                elif isinstance(item, str):
                    entities[item.strip().replace(" ", "_")] = "block"

        def _parse_facts(raw_list: Any) -> List[FactSchema]:
            facts: List[FactSchema] = []
            if not isinstance(raw_list, list):
                return facts
            for f in raw_list:
                if isinstance(f, dict) and "predicate" in f and "arguments" in f:
                    pred = str(f["predicate"]).strip().rstrip("()").strip()
                    args = tuple(str(a).strip().replace(" ", "_").rstrip("()") for a in f["arguments"])
                    facts.append(FactSchema(predicate=pred, arguments=args))
                elif isinstance(f, str):
                    # Regex for pred(arg1, arg2)
                    clean_str = f.strip()
                    m = re.match(r"^(\w+)\(([^)]*)\)$", clean_str)
                    if m:
                        pred = m.group(1).strip().rstrip("()").strip()
                        args = tuple(a.strip().replace(" ", "_").rstrip("()") for a in m.group(2).split(",") if a.strip())
                        facts.append(FactSchema(predicate=pred, arguments=args))
                    elif clean_str.rstrip("()") == "handempty":
                        facts.append(FactSchema(predicate="handempty", arguments=()))
                    elif "on_table" in clean_str or "table" in clean_str:
                        for token in clean_str.lower().split():
                            if "box" in token or "block" in token:
                                facts.append(FactSchema(predicate="on_table", arguments=(token.strip(".,;:()").replace(" ", "_"),)))
                                break
                    elif "clear" in clean_str:
                        for token in clean_str.lower().split():
                            if "box" in token or "block" in token:
                                facts.append(FactSchema(predicate="clear", arguments=(token.strip(".,;:()").replace(" ", "_"),)))
                                break
            return facts

        raw_initial_facts = _parse_facts(parsed.get("initial_facts", []))
        raw_goal_facts = _parse_facts(parsed.get("goal_facts", []))
        raw_negative_constraints = _parse_facts(parsed.get("negative_constraints", []))
        invariants = _parse_facts(parsed.get("invariants", []))

        # 1. Map predicates in raw_negative_constraints:
        # e.g. "touching", "touch", "move", "moving", "lift", "lifting", "manipulate" -> "holding"
        negative_constraints = []
        for f in raw_negative_constraints:
            pred = f.predicate.lower().rstrip("()")
            if pred in ("touching", "touch", "move", "moving", "lift", "lifting", "manipulate", "manipulating", "take", "taking"):
                pred = "holding"
            if pred in ("holding", "on"):
                negative_constraints.append(FactSchema(predicate=pred, arguments=f.arguments))

        # 2. Filter intermediate holding(A) in goal_facts when on(A, B) is also requested
        stacked_in_goal = {f.arguments[0] for f in raw_goal_facts if f.predicate.lower().rstrip("()") == "on" and f.arguments}
        goal_facts = [
            f for f in raw_goal_facts
            if not (f.predicate.lower().rstrip("()") == "holding" and f.arguments and f.arguments[0] in stacked_in_goal)
        ]

        # 3. Prevent contradiction: If an object is forbidden in negative_constraints (e.g. holding(glass)),
        # it should NOT be in initial holding facts unless prompt explicitly says the robot is holding it.
        forbidden_held = {f.arguments[0] for f in negative_constraints if f.predicate.lower().rstrip("()") == "holding" and f.arguments}
        prompt_lower = prompt.lower()

        initial_facts: List[FactSchema] = []
        has_held = False
        has_handempty = False

        for f in raw_initial_facts:
            pred = f.predicate.lower().rstrip("()")
            if pred == "holding" and f.arguments:
                held_arg = f.arguments[0]
                if held_arg in forbidden_held and "currently holding" not in prompt_lower and "is holding" not in prompt_lower:
                    # Model hallucinated held object that was meant to be a negative constraint
                    initial_facts.append(FactSchema(predicate="on_table", arguments=(held_arg,)))
                    initial_facts.append(FactSchema(predicate="clear", arguments=(held_arg,)))
                    continue
                has_held = True
            elif pred == "handempty":
                has_handempty = True
            initial_facts.append(FactSchema(predicate=pred, arguments=f.arguments))

        if not has_held and not has_handempty:
            initial_facts.append(FactSchema(predicate="handempty", arguments=()))

        # First: Ensure all referenced arguments across all facts exist in entities dictionary
        for fact in raw_initial_facts + goal_facts + negative_constraints + invariants:
            for arg in fact.arguments:
                clean_arg = arg.strip().replace(" ", "_").rstrip("()")
                if clean_arg and clean_arg not in entities:
                    entities[clean_arg] = "block"

        # Second: Ensure all entities have initial support
        placed_entities = {f.arguments[0] for f in initial_facts if f.predicate.lower() in ("on_table", "on", "holding") and f.arguments}
        for ent in list(entities.keys()):
            if ent not in placed_entities:
                initial_facts.append(FactSchema(predicate="on_table", arguments=(ent,)))
                initial_facts.append(FactSchema(predicate="clear", arguments=(ent,)))

        # Third: Deduplicate initial_facts and goal_facts
        def _dedup(facts_list: List[FactSchema]) -> List[FactSchema]:
            seen: Set[Tuple[str, Tuple[str, ...]]] = set()
            out: List[FactSchema] = []
            for item in facts_list:
                k = (item.predicate.lower().rstrip("()"), tuple(item.arguments))
                if k not in seen:
                    seen.add(k)
                    out.append(FactSchema(predicate=k[0], arguments=item.arguments))
            return out

        initial_facts = _dedup(initial_facts)
        goal_facts = _dedup(goal_facts)

        return TaskProposalSchema(
            task_id=str(parsed.get("task_id", "task_formalized")),
            raw_prompt=prompt,
            entities=entities,
            initial_facts=initial_facts,
            goal_facts=goal_facts,
            negative_constraints=negative_constraints,
            invariants=invariants,
            confidence=float(parsed.get("confidence", 0.95)),
        )
