"""Dynamic reactive replanner handling relevant environment changes."""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple
from core.actions.domain import Domain
from core.contracts import FactSchema, PlanSchema, WorldDeltaSchema
from core.replanning.loop import ReplanningEngine
from core.verification.verifier import PlanVerifier
from core.world.predicates import Fact
from core.world.problem import SymbolicProblem
from core.world.state import SymbolicState
from dynamic.monitor import WorldDeltaMonitor


class DynamicReplanner:
    """Evaluates world deltas and conditionally replans only when remaining plan is invalidated."""

    def __init__(
        self,
        monitor: Optional[WorldDeltaMonitor] = None,
        verifier: Optional[PlanVerifier] = None,
        replanning_engine: Optional[ReplanningEngine] = None,
    ) -> None:
        self.monitor = monitor or WorldDeltaMonitor()
        self.verifier = verifier or PlanVerifier()
        self.replanning_engine = replanning_engine or ReplanningEngine()

    def process_observation(
        self,
        current_state: SymbolicState,
        remaining_plan: PlanSchema,
        problem: SymbolicProblem,
        domain: Domain,
        new_observation_facts: Sequence[FactSchema],
    ) -> Tuple[bool, PlanSchema, WorldDeltaSchema]:
        """Processes new observation.

        Returns:
            (replan_triggered: bool, active_plan: PlanSchema, delta: WorldDeltaSchema)
        """
        delta = self.monitor.compute_delta(current_state, new_observation_facts)

        # Apply delta to update belief state
        adds = [Fact.from_schema(f) for f in delta.added_facts]
        dels = [Fact.from_schema(f) for f in delta.removed_facts]
        updated_state = current_state.apply_effects(adds=adds, dels=dels)

        # Construct updated problem with new initial state
        updated_problem = SymbolicProblem(
            name=f"{problem.name}_dynamic",
            domain_name=problem.domain_name,
            registry=problem.registry,
            initial_state=updated_state,
            goal_conditions=problem.goal_conditions,
            invariants=problem.invariants,
            hard_constraints=problem.hard_constraints,
        )

        # Verify whether remaining plan still executes and achieves goal
        v_res = self.verifier.verify(updated_problem, domain, remaining_plan)

        if v_res.is_valid:
            # Change is IRRELEVANT: do not trigger replanning
            delta.is_plan_invalidating = False
            delta.explanation += " Change is IRRELEVANT: remaining plan remains fully valid."
            return False, remaining_plan, delta

        # Change is RELEVANT: plan was invalidated
        delta.is_plan_invalidating = True
        delta.invalidated_action_index = v_res.failed_step_index
        delta.explanation += f" Change is RELEVANT: plan failed at step {v_res.failed_step_index} ({v_res.explanation})."

        # Replan from updated state using repair loop
        replan_res = self.replanning_engine.run_repair_loop(
            problem=updated_problem,
            domain=domain,
            initial_candidate=None,  # Search for fresh plan from updated state
        )

        new_plan = replan_res.repaired_plan or remaining_plan
        return True, new_plan, delta
