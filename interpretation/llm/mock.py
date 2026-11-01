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
        domain_id = getattr(domain, "domain_id", getattr(domain, "name", "blocks_world")).lower()

        # Multi-domain dispatch for non-blocks registered domains
        if domain_id not in ("blocks_world", "blocks"):
            from interpretation.router import DomainRouter, RoutingOutcome
            router = DomainRouter()
            routing = router.route(prompt, explicit_domain_id=domain_id)
            if routing.outcome == RoutingOutcome.SUPPORTED:
                return TaskProposalSchema(
                    task_id=f"mock_{domain_id}_task",
                    raw_prompt=prompt,
                    entities=routing.entities,
                    initial_facts=routing.initial_facts,
                    goal_facts=routing.goal_facts,
                    negative_constraints=routing.negative_constraints,
                    confidence=routing.domain_confidence,
                )

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
        if "inversion" in prompt_lower or ("unstack" in prompt_lower and "invert" in prompt_lower) or "unstack the red" in prompt_lower or ("red box is on the green box" in prompt_lower and "stack the green" in prompt_lower):
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

        # 7. Contradictory / Deadlock scenario (Circular simultaneous dependency)
        if (("simultaneously" in prompt_lower or "cycle" in prompt_lower or "circular" in prompt_lower) and ("green" in prompt_lower or "each other" in prompt_lower or "both" in prompt_lower)) or ("red box on the green box and the green box on the red" in prompt_lower):
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

        # 7a. Unsupported Operator / Predicate (e.g. "teleport" or "fly")
        if "teleport" in prompt_lower or "fly" in prompt_lower:
            entities = {"red_box": "block", "blue_box": "block"}
            return TaskProposalSchema(
                task_id="mock_unsupported_operator",
                raw_prompt=prompt,
                entities=entities,
                initial_facts=[
                    FactSchema(predicate="on_table", arguments=("red_box",)),
                    FactSchema(predicate="clear", arguments=("red_box",)),
                    FactSchema(predicate="handempty", arguments=()),
                ],
                goal_facts=[FactSchema(predicate="teleported_to", arguments=("red_box", "blue_box"))],
                confidence=0.9,
            )

        # 7b. Mutex Contradiction in Initial State (holding object while handempty)
        if "hand is empty while holding" in prompt_lower or "holding and hand is empty" in prompt_lower or "simultaneously holding and handempty" in prompt_lower:
            entities = {"red_box": "block"}
            return TaskProposalSchema(
                task_id="mock_mutex_contradiction",
                raw_prompt=prompt,
                entities=entities,
                initial_facts=[
                    FactSchema(predicate="holding", arguments=("red_box",)),
                    FactSchema(predicate="handempty", arguments=()),
                ],
                goal_facts=[FactSchema(predicate="on_table", arguments=("red_box",))],
                confidence=0.9,
            )

        # 7c. Direct Goal vs Negative Constraint Contradiction
        if "never place red" in prompt_lower or "never stack red on blue" in prompt_lower or "do not put red on blue" in prompt_lower or "forbidden to put red on blue" in prompt_lower:
            entities = {"red_box": "block", "blue_box": "block"}
            return TaskProposalSchema(
                task_id="mock_goal_constraint_contradiction",
                raw_prompt=prompt,
                entities=entities,
                initial_facts=[
                    FactSchema(predicate="on_table", arguments=("red_box",)),
                    FactSchema(predicate="clear", arguments=("red_box",)),
                    FactSchema(predicate="on_table", arguments=("blue_box",)),
                    FactSchema(predicate="clear", arguments=("blue_box",)),
                    FactSchema(predicate="handempty", arguments=()),
                ],
                goal_facts=[FactSchema(predicate="on", arguments=("red_box", "blue_box"))],
                negative_constraints=[FactSchema(predicate="on", arguments=("red_box", "blue_box"))],
                confidence=0.9,
            )

        # 7d. Self-stacking cycle (A on A)
        if "on itself" in prompt_lower or "on top of itself" in prompt_lower or "red box on the red box" in prompt_lower or "red box on red box" in prompt_lower:
            entities = {"red_box": "block"}
            return TaskProposalSchema(
                task_id="mock_self_stack_deadlock",
                raw_prompt=prompt,
                entities=entities,
                initial_facts=[
                    FactSchema(predicate="on_table", arguments=("red_box",)),
                    FactSchema(predicate="clear", arguments=("red_box",)),
                    FactSchema(predicate="handempty", arguments=()),
                ],
                goal_facts=[FactSchema(predicate="on", arguments=("red_box", "red_box"))],
                confidence=0.5,
            )

        # 7e. Total Action Blockade (Deadlock by over-constraint)
        if "without touching any block" in prompt_lower or "never touch any block" in prompt_lower:
            entities = {"red_box": "block", "blue_box": "block"}
            return TaskProposalSchema(
                task_id="mock_total_blockade_deadlock",
                raw_prompt=prompt,
                entities=entities,
                initial_facts=[
                    FactSchema(predicate="on_table", arguments=("red_box",)),
                    FactSchema(predicate="clear", arguments=("red_box",)),
                    FactSchema(predicate="on_table", arguments=("blue_box",)),
                    FactSchema(predicate="clear", arguments=("blue_box",)),
                    FactSchema(predicate="handempty", arguments=()),
                ],
                goal_facts=[FactSchema(predicate="on", arguments=("red_box", "blue_box"))],
                negative_constraints=[
                    FactSchema(predicate="holding", arguments=("red_box",)),
                    FactSchema(predicate="holding", arguments=("blue_box",)),
                ],
                confidence=0.8,
            )

        # 7f. Predicate Arity Mismatch (e.g. on_table expecting 1 arg, given 2)
        if "surface" in prompt_lower or "arity" in prompt_lower:
            entities = {"red_box": "block", "table_surface": "block"}
            return TaskProposalSchema(
                task_id="mock_arity_mismatch",
                raw_prompt=prompt,
                entities=entities,
                initial_facts=[
                    FactSchema(predicate="on_table", arguments=("red_box", "table_surface")),
                    FactSchema(predicate="clear", arguments=("red_box",)),
                    FactSchema(predicate="handempty", arguments=()),
                ],
                goal_facts=[FactSchema(predicate="clear", arguments=("table_surface",))],
                confidence=0.8,
            )

        # 7g. Buried target with forbidden unstacking
        if "buried" in prompt_lower or ("bottom block" in prompt_lower and "forbidden" in prompt_lower):
            entities = {"top_box": "block", "bottom_box": "block"}
            return TaskProposalSchema(
                task_id="mock_buried_target_deadlock",
                raw_prompt=prompt,
                entities=entities,
                initial_facts=[
                    FactSchema(predicate="on_table", arguments=("bottom_box",)),
                    FactSchema(predicate="on", arguments=("top_box", "bottom_box")),
                    FactSchema(predicate="clear", arguments=("top_box",)),
                    FactSchema(predicate="handempty", arguments=()),
                ],
                goal_facts=[FactSchema(predicate="holding", arguments=("bottom_box",))],
                negative_constraints=[
                    FactSchema(predicate="holding", arguments=("top_box",)),
                ],
                confidence=0.8,
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

        # Dynamic router formalization for general blocks world prompts before static fallback
        from interpretation.router import DomainRouter, RoutingOutcome
        router = DomainRouter()
        routing = router.route(prompt, explicit_domain_id="blocks_world")
        if routing.outcome == RoutingOutcome.SUPPORTED and routing.entities and routing.goal_facts:
            return TaskProposalSchema(
                task_id="mock_router_blocks_task",
                raw_prompt=prompt,
                entities=routing.entities,
                initial_facts=routing.initial_facts,
                goal_facts=routing.goal_facts,
                negative_constraints=routing.negative_constraints,
                confidence=routing.domain_confidence,
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

