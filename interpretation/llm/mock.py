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

        # 1. 4-Block Tower Assembly
        if "4-block" in prompt_lower or ("yellow" in prompt_lower and "green" in prompt_lower and "blue" in prompt_lower and "red" in prompt_lower):
            entities = {
                "yellow_box": "block",
                "green_box": "block",
                "blue_box": "block",
                "red_box": "block",
            }
            initial_facts = [
                FactSchema(predicate="on_table", arguments=("yellow_box",)),
                FactSchema(predicate="clear", arguments=("yellow_box",)),
                FactSchema(predicate="on_table", arguments=("green_box",)),
                FactSchema(predicate="clear", arguments=("green_box",)),
                FactSchema(predicate="on_table", arguments=("blue_box",)),
                FactSchema(predicate="clear", arguments=("blue_box",)),
                FactSchema(predicate="on_table", arguments=("red_box",)),
                FactSchema(predicate="clear", arguments=("red_box",)),
                FactSchema(predicate="handempty", arguments=()),
            ]
            goal_facts = [
                FactSchema(predicate="on", arguments=("blue_box", "red_box")),
                FactSchema(predicate="on", arguments=("green_box", "blue_box")),
                FactSchema(predicate="on", arguments=("yellow_box", "green_box")),
            ]
            return TaskProposalSchema(
                task_id="mock_4block_tower",
                raw_prompt=prompt,
                entities=entities,
                initial_facts=initial_facts,
                goal_facts=goal_facts,
                confidence=1.0,
            )

        # 2. Tower Inversion / Deconstruction & Reconstruction
        if "unstack" in prompt_lower or "inversion" in prompt_lower or ("red box is on the green box" in prompt_lower and "stack the green" in prompt_lower):
            entities = {"red_box": "block", "green_box": "block"}
            initial_facts = [
                FactSchema(predicate="on_table", arguments=("green_box",)),
                FactSchema(predicate="on", arguments=("red_box", "green_box")),
                FactSchema(predicate="clear", arguments=("red_box",)),
                FactSchema(predicate="handempty", arguments=()),
            ]
            goal_facts = [
                FactSchema(predicate="on_table", arguments=("red_box",)),
                FactSchema(predicate="on", arguments=("green_box", "red_box")),
            ]
            return TaskProposalSchema(
                task_id="mock_tower_inversion",
                raw_prompt=prompt,
                entities=entities,
                initial_facts=initial_facts,
                goal_facts=goal_facts,
                confidence=0.98,
            )

        # 3. Clear Obstacle before Stacking
        if "obstacle" in prompt_lower:
            entities = {"obstacle": "block", "blue_box": "block", "green_box": "block"}
            initial_facts = [
                FactSchema(predicate="on_table", arguments=("green_box",)),
                FactSchema(predicate="on", arguments=("obstacle", "green_box")),
                FactSchema(predicate="clear", arguments=("obstacle",)),
                FactSchema(predicate="on_table", arguments=("blue_box",)),
                FactSchema(predicate="clear", arguments=("blue_box",)),
                FactSchema(predicate="handempty", arguments=()),
            ]
            goal_facts = [
                FactSchema(predicate="on", arguments=("blue_box", "green_box")),
                FactSchema(predicate="on_table", arguments=("obstacle",)),
            ]
            return TaskProposalSchema(
                task_id="mock_obstacle_clearing",
                raw_prompt=prompt,
                entities=entities,
                initial_facts=initial_facts,
                goal_facts=goal_facts,
                confidence=0.98,
            )

        # 4. Multi-tier 3-Block Tower (e.g. Red, Green, Blue)
        if ("red" in prompt_lower and "green" in prompt_lower and "blue" in prompt_lower) or "3-block" in prompt_lower or "three-block" in prompt_lower:
            entities = {
                "red_box": "block",
                "green_box": "block",
                "blue_box": "block",
            }
            initial_facts = [
                FactSchema(predicate="on_table", arguments=("red_box",)),
                FactSchema(predicate="clear", arguments=("red_box",)),
                FactSchema(predicate="on_table", arguments=("green_box",)),
                FactSchema(predicate="clear", arguments=("green_box",)),
                FactSchema(predicate="on_table", arguments=("blue_box",)),
                FactSchema(predicate="clear", arguments=("blue_box",)),
                FactSchema(predicate="handempty", arguments=()),
            ]
            goal_facts = [
                FactSchema(predicate="on", arguments=("red_box", "green_box")),
                FactSchema(predicate="on", arguments=("blue_box", "red_box")),
            ]
            return TaskProposalSchema(
                task_id="mock_3block_tower",
                raw_prompt=prompt,
                entities=entities,
                initial_facts=initial_facts,
                goal_facts=goal_facts,
                confidence=1.0,
            )

        # 5. Fragile Object Negative Constraint (e.g. glass/vase)
        if ("glass" in prompt_lower or "fragile" in prompt_lower) and "blue" in prompt_lower and "green" in prompt_lower:
            entities = {"blue_box": "block", "green_box": "block", "glass": "block"}
            initial_facts = [
                FactSchema(predicate="on_table", arguments=("blue_box",)),
                FactSchema(predicate="clear", arguments=("blue_box",)),
                FactSchema(predicate="on_table", arguments=("green_box",)),
                FactSchema(predicate="clear", arguments=("green_box",)),
                FactSchema(predicate="on_table", arguments=("glass",)),
                FactSchema(predicate="clear", arguments=("glass",)),
                FactSchema(predicate="handempty", arguments=()),
            ]
            goal_facts = [FactSchema(predicate="on", arguments=("blue_box", "green_box"))]
            negative_constraints = [FactSchema(predicate="holding", arguments=("glass",))]
            return TaskProposalSchema(
                task_id="mock_fragile_constraint",
                raw_prompt=prompt,
                entities=entities,
                initial_facts=initial_facts,
                goal_facts=goal_facts,
                negative_constraints=negative_constraints,
                confidence=1.0,
            )

        # 6. Single-Arm Invariant / Pick up only
        if "pick up" in prompt_lower and ("single-arm" in prompt_lower or "capacity" in prompt_lower or "workspace" in prompt_lower):
            entities = {"red_box": "block"}
            initial_facts = [
                FactSchema(predicate="on_table", arguments=("red_box",)),
                FactSchema(predicate="clear", arguments=("red_box",)),
                FactSchema(predicate="handempty", arguments=()),
            ]
            goal_facts = [FactSchema(predicate="holding", arguments=("red_box",))]
            return TaskProposalSchema(
                task_id="mock_pickup_task",
                raw_prompt=prompt,
                entities=entities,
                initial_facts=initial_facts,
                goal_facts=goal_facts,
                confidence=0.98,
            )

        # 7. Contradictory / Deadlock scenario
        if "simultaneously" in prompt_lower or ("red box on the green box and the green box on the red" in prompt_lower):
            entities = {"red_box": "block", "green_box": "block"}
            initial_facts = [
                FactSchema(predicate="on_table", arguments=("red_box",)),
                FactSchema(predicate="clear", arguments=("red_box",)),
                FactSchema(predicate="on_table", arguments=("green_box",)),
                FactSchema(predicate="clear", arguments=("green_box",)),
                FactSchema(predicate="handempty", arguments=()),
            ]
            # Mutually contradictory goals
            goal_facts = [
                FactSchema(predicate="on", arguments=("red_box", "green_box")),
                FactSchema(predicate="on", arguments=("green_box", "red_box")),
            ]
            return TaskProposalSchema(
                task_id="mock_deadlock_conflict",
                raw_prompt=prompt,
                entities=entities,
                initial_facts=initial_facts,
                goal_facts=goal_facts,
                confidence=0.5,
            )

        # 8. Canonical DoD prompt: "Move the red box next to the blue box. Do not move the glass."
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
            negative_constraints = []
            if "do not move the glass" in prompt_lower or "do not touch glass" in prompt_lower or "do not" in prompt_lower:
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

            neg_match = re.search(r"do not (?:move|touch|hold)\s+([a-zA-Z0-9_]+)", prompt_lower)
            negative_constraints = []
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

