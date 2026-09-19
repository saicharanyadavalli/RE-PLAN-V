"""Deterministic Mock LLM Provider for offline testing and evaluation."""

from __future__ import annotations

import re
from typing import Dict, List, Optional
from core.actions.domain import Domain
from core.contracts import FactSchema, TaskProposalSchema
from interpretation.llm.base import BaseLLMProvider


class MockLLMProvider(BaseLLMProvider):
    """Deterministic, zero-API rule-based language interpreter for testing and benchmarks."""

    def interpret(self, prompt: str, domain: Domain) -> TaskProposalSchema:
        prompt_lower = prompt.lower().strip()
        entities: Dict[str, str] = {}
        initial_facts: List[FactSchema] = []
        goal_facts: List[FactSchema] = []
        negative_constraints: List[FactSchema] = []

        # Canonical example from Definition of Done:
        # "Move the red box next to the blue box. Do not move the glass."
        if "red" in prompt_lower and "blue" in prompt_lower:
            entities = {
                "red_box": "block",
                "blue_box": "block",
                "glass": "block",
            }
            initial_facts = [
                FactSchema(predicate="on_table", arguments=("red_box",)),
                FactSchema(predicate="clear", arguments=("red_box",)),
                FactSchema(predicate="on_table", arguments=("blue_box",)),
                FactSchema(predicate="clear", arguments=("blue_box",)),
                FactSchema(predicate="on_table", arguments=("glass",)),
                FactSchema(predicate="clear", arguments=("glass",)),
                FactSchema(predicate="handempty", arguments=()),
            ]
            goal_facts = [
                FactSchema(predicate="on", arguments=("red_box", "blue_box")),
            ]
            if "do not move the glass" in prompt_lower or "do not touch glass" in prompt_lower:
                negative_constraints = [
                    FactSchema(predicate="holding", arguments=("glass",)),
                ]

            return TaskProposalSchema(
                task_id="mock_dod_task",
                raw_prompt=prompt,
                entities=entities,
                initial_facts=initial_facts,
                goal_facts=goal_facts,
                negative_constraints=negative_constraints,
                confidence=1.0,
            )

        # Standard Blocks Stacking prompt: e.g. "stack b1 on b2" or "put b1 on b2"
        stack_match = re.search(r"(?:stack|put|move)\s+([a-zA-Z0-9_]+)\s+on\s+([a-zA-Z0-9_]+)", prompt_lower)
        if stack_match:
            top_obj = stack_match.group(1)
            bot_obj = stack_match.group(2)
            entities = {top_obj: "block", bot_obj: "block"}
            initial_facts = [
                FactSchema(predicate="on_table", arguments=(top_obj,)),
                FactSchema(predicate="clear", arguments=(top_obj,)),
                FactSchema(predicate="on_table", arguments=(bot_obj,)),
                FactSchema(predicate="clear", arguments=(bot_obj,)),
                FactSchema(predicate="handempty", arguments=()),
            ]
            goal_facts = [FactSchema(predicate="on", arguments=(top_obj, bot_obj))]

            # Check for negative constraints
            neg_match = re.search(r"do not (?:move|touch|hold)\s+([a-zA-Z0-9_]+)", prompt_lower)
            if neg_match:
                prot_obj = neg_match.group(1)
                entities[prot_obj] = "block"
                initial_facts.extend([
                    FactSchema(predicate="on_table", arguments=(prot_obj,)),
                    FactSchema(predicate="clear", arguments=(prot_obj,)),
                ])
                negative_constraints.append(FactSchema(predicate="holding", arguments=(prot_obj,)))

            return TaskProposalSchema(
                task_id="mock_stack_task",
                raw_prompt=prompt,
                entities=entities,
                initial_facts=initial_facts,
                goal_facts=goal_facts,
                negative_constraints=negative_constraints,
                confidence=0.95,
            )

        # Default fallback proposal
        entities = {"b1": "block", "b2": "block"}
        initial_facts = [
            FactSchema(predicate="on_table", arguments=("b1",)),
            FactSchema(predicate="clear", arguments=("b1",)),
            FactSchema(predicate="on_table", arguments=("b2",)),
            FactSchema(predicate="clear", arguments=("b2",)),
            FactSchema(predicate="handempty", arguments=()),
        ]
        goal_facts = [FactSchema(predicate="on", arguments=("b1", "b2"))]

        return TaskProposalSchema(
            task_id="mock_fallback_task",
            raw_prompt=prompt,
            entities=entities,
            initial_facts=initial_facts,
            goal_facts=goal_facts,
            negative_constraints=[],
            confidence=0.80,
        )
