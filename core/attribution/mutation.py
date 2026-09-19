"""Controlled fault injection and mutation engine for attribution evaluation."""

from __future__ import annotations

import random
from typing import List, Optional, Sequence, Tuple
from core.contracts import (
    FactSchema,
    FaultClass,
    GroundActionSchema,
    PlanSchema,
    WorldDeltaSchema,
)
from core.world.constraints import ProhibitedEntityActionConstraint
from core.world.predicates import Fact
from core.world.problem import SymbolicProblem
from core.world.state import SymbolicState


class FaultInjector:
    """Injects controlled ground-truth faults to evaluate attribution and repair mechanisms."""

    def __init__(self, seed: int = 42) -> None:
        self.rng = random.Random(seed)

    def inject_planning_error(self, valid_plan: PlanSchema) -> PlanSchema:
        """Mutates a valid plan by swapping or corrupting an action."""
        if not valid_plan.actions:
            return valid_plan

        actions = list(valid_plan.actions)
        if len(actions) >= 2:
            # Reverse order of first two actions
            actions[0], actions[1] = actions[1], actions[0]
        else:
            # Corrupt parameters
            a0 = actions[0]
            mutated_args = tuple(reversed(a0.arguments)) if a0.arguments else ("corrupted_obj",)
            actions[0] = GroundActionSchema(name=a0.name, arguments=mutated_args, cost=a0.cost)

        return PlanSchema(
            actions=actions,
            algorithm=valid_plan.algorithm,
            total_cost=valid_plan.total_cost,
            is_success=True,
        )

    def inject_perception_error(
        self, true_facts: Sequence[FactSchema]
    ) -> Tuple[List[FactSchema], List[FactSchema]]:
        """Simulates perceptual error by hallucinating a non-existent fact or dropping a real fact."""
        gt_facts = list(true_facts)
        perceived_facts = list(true_facts)

        if perceived_facts:
            # Drop a critical fact from perceived facts
            dropped = perceived_facts.pop(0)
            # Add a hallucinated fact
            hallucinated = FactSchema(predicate="clear", arguments=("hallucinated_block",), is_negated=False)
            perceived_facts.append(hallucinated)

        return perceived_facts, gt_facts

    def inject_formalization_error(
        self, problem: SymbolicProblem, protected_entity: str = "glass"
    ) -> Tuple[SymbolicProblem, str]:
        """Creates a problem that omitted the user prompt's safety constraint."""
        prompt = f"Move the red box next to the blue box. Do not move the {protected_entity}."
        # Strip any hard constraints protecting this entity
        stripped_constraints = [
            hc for hc in problem.hard_constraints
            if protected_entity.lower() not in hc.name.lower()
        ]
        corrupted_problem = SymbolicProblem(
            name=f"{problem.name}_formalization_err",
            domain_name=problem.domain_name,
            registry=problem.registry,
            initial_state=problem.initial_state,
            goal_conditions=problem.goal_conditions,
            invariants=problem.invariants,
            hard_constraints=stripped_constraints,
            description=problem.description,
        )
        return corrupted_problem, prompt

    def inject_environment_change(
        self, state: SymbolicState, target_fact: Fact
    ) -> Tuple[SymbolicState, WorldDeltaSchema]:
        """Simulates an external environment perturbation by modifying a fact."""
        new_state = state.apply_effects(adds=[], dels=[target_fact])
        delta = WorldDeltaSchema(
            delta_id="DELTA-MUTATION-01",
            added_facts=[],
            removed_facts=[target_fact.to_schema()],
            affected_entities=list(target_fact.arguments),
            is_plan_invalidating=True,
            explanation=f"External perturbation removed fact: {target_fact.to_string()}",
        )
        return new_state, delta
