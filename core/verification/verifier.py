"""Independent, deterministic formal plan verifier.

Checks precondition satisfaction, authoritative state transitions, invariant preservation,
hard safety constraints, and goal attainment.
"""

from __future__ import annotations

import time
from typing import List, Optional, Sequence, Union

from core.actions.domain import Domain
from core.actions.instantiation import GroundAction
from core.actions.transition import apply_transition
from core.contracts import (
    FactSchema,
    GroundActionSchema,
    PlanSchema,
    SymbolicStateSchema,
    VerificationResultSchema,
    VerificationTraceStep,
    ViolationType,
)
from core.world.predicates import Fact
from core.world.problem import SymbolicProblem
from core.world.state import SymbolicState


class PlanVerifier:
    """Authoritative verifier for candidate plans."""

    def verify(
        self,
        problem: SymbolicProblem,
        domain: Domain,
        plan: Union[PlanSchema, Sequence[GroundActionSchema], Sequence[GroundAction]],
    ) -> VerificationResultSchema:
        start_time = time.perf_counter()

        # Extract sequence of actions
        raw_actions: Sequence[Union[GroundActionSchema, GroundAction]]
        if isinstance(plan, PlanSchema):
            raw_actions = plan.actions
        else:
            raw_actions = plan

        current_state: SymbolicState = problem.initial_state
        trace: List[VerificationTraceStep] = []

        # 0. Initial state invariant check
        ok_init_inv, init_msg = problem.check_invariants(current_state)
        if not ok_init_inv:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return VerificationResultSchema(
                is_valid=False,
                failed_step_index=0,
                violation_type=ViolationType.INVARIANT_VIOLATED,
                pre_state=current_state.to_schema(),
                trace=trace,
                verification_time_ms=elapsed_ms,
                explanation=f"Initial state violates invariant: {init_msg}",
            )

        for step_idx, act_item in enumerate(raw_actions):
            # Resolve to GroundAction with domain semantics
            act_name = act_item.name
            act_args = tuple(act_item.arguments)
            action_def = domain.get_action(act_name)

            if action_def is None:
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                trace.append(
                    VerificationTraceStep(
                        step_index=step_idx,
                        action=GroundActionSchema(name=act_name, arguments=act_args),
                        pre_state_facts_count=len(current_state.facts),
                        post_state_facts_count=len(current_state.facts),
                        is_valid=False,
                        violation=f"Action '{act_name}' not defined in domain",
                    )
                )
                return VerificationResultSchema(
                    is_valid=False,
                    failed_step_index=step_idx,
                    failed_action=GroundActionSchema(name=act_name, arguments=act_args),
                    violation_type=ViolationType.INVALID_ACTION,
                    pre_state=current_state.to_schema(),
                    trace=trace,
                    verification_time_ms=elapsed_ms,
                    explanation=f"Action operator '{act_name}' is not recognized in domain '{domain.name}'.",
                )

            # Build binding for the action definition
            if len(act_args) != len(action_def.parameters):
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                return VerificationResultSchema(
                    is_valid=False,
                    failed_step_index=step_idx,
                    failed_action=GroundActionSchema(name=act_name, arguments=act_args),
                    violation_type=ViolationType.INVALID_ACTION,
                    pre_state=current_state.to_schema(),
                    trace=trace,
                    verification_time_ms=elapsed_ms,
                    explanation=f"Action '{act_name}' arity mismatch: expected {len(action_def.parameters)}, got {len(act_args)}.",
                )

            binding = {param.name: arg for param, arg in zip(action_def.parameters, act_args)}
            ground_action = action_def.instantiate(binding)

            # 1. Check Hard Constraints
            ok_hc, hc_msg = problem.check_hard_constraints(current_state, act_name, act_args)
            if not ok_hc:
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                trace.append(
                    VerificationTraceStep(
                        step_index=step_idx,
                        action=ground_action.to_schema(),
                        pre_state_facts_count=len(current_state.facts),
                        post_state_facts_count=len(current_state.facts),
                        is_valid=False,
                        violation=hc_msg,
                    )
                )
                return VerificationResultSchema(
                    is_valid=False,
                    failed_step_index=step_idx,
                    failed_action=ground_action.to_schema(),
                    violation_type=ViolationType.HARD_CONSTRAINT_VIOLATED,
                    pre_state=current_state.to_schema(),
                    trace=trace,
                    verification_time_ms=elapsed_ms,
                    explanation=f"Step {step_idx}: {hc_msg}",
                )

            # 2. Check Preconditions
            is_applicable, unmet_pre = ground_action.is_applicable(current_state)
            if not is_applicable and unmet_pre is not None:
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                trace.append(
                    VerificationTraceStep(
                        step_index=step_idx,
                        action=ground_action.to_schema(),
                        pre_state_facts_count=len(current_state.facts),
                        post_state_facts_count=len(current_state.facts),
                        is_valid=False,
                        violation=f"Precondition {unmet_pre.to_string()} unmet",
                    )
                )
                return VerificationResultSchema(
                    is_valid=False,
                    failed_step_index=step_idx,
                    failed_action=ground_action.to_schema(),
                    violated_condition=unmet_pre.to_schema(),
                    violation_type=ViolationType.PRECONDITION_UNMET,
                    pre_state=current_state.to_schema(),
                    trace=trace,
                    verification_time_ms=elapsed_ms,
                    explanation=f"Step {step_idx} ({ground_action.to_string()}): Precondition '{unmet_pre.to_string()}' is not satisfied.",
                )

            # 3. Apply Authoritative Transition
            next_state, trans_err = apply_transition(current_state, ground_action)
            if trans_err is not None:
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                return VerificationResultSchema(
                    is_valid=False,
                    failed_step_index=step_idx,
                    failed_action=ground_action.to_schema(),
                    violation_type=ViolationType.PRECONDITION_UNMET,
                    pre_state=current_state.to_schema(),
                    trace=trace,
                    verification_time_ms=elapsed_ms,
                    explanation=f"Step {step_idx}: Transition failed with error: {trans_err}",
                )

            # 4. Check Invariants on Post-State
            ok_inv, inv_msg = problem.check_invariants(next_state)
            if not ok_inv:
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                trace.append(
                    VerificationTraceStep(
                        step_index=step_idx,
                        action=ground_action.to_schema(),
                        pre_state_facts_count=len(current_state.facts),
                        post_state_facts_count=len(next_state.facts),
                        is_valid=False,
                        violation=inv_msg,
                    )
                )
                return VerificationResultSchema(
                    is_valid=False,
                    failed_step_index=step_idx,
                    failed_action=ground_action.to_schema(),
                    violation_type=ViolationType.INVARIANT_VIOLATED,
                    pre_state=current_state.to_schema(),
                    post_state=next_state.to_schema(),
                    trace=trace,
                    verification_time_ms=elapsed_ms,
                    explanation=f"Step {step_idx}: Invariant violated after executing '{ground_action.to_string()}': {inv_msg}",
                )

            # Step succeeded
            trace.append(
                VerificationTraceStep(
                    step_index=step_idx,
                    action=ground_action.to_schema(),
                    pre_state_facts_count=len(current_state.facts),
                    post_state_facts_count=len(next_state.facts),
                    is_valid=True,
                )
            )
            current_state = next_state

        # 5. Check Goal Satisfaction on Final State
        is_goal_met = problem.is_goal_satisfied(current_state)
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        if not is_goal_met:
            unmet_goals = problem.find_unmet_goals(current_state)
            first_unmet = unmet_goals[0] if unmet_goals else None
            return VerificationResultSchema(
                is_valid=False,
                failed_step_index=len(raw_actions),
                violated_condition=first_unmet.to_schema() if first_unmet else None,
                violation_type=ViolationType.GOAL_UNMET,
                post_state=current_state.to_schema(),
                trace=trace,
                verification_time_ms=elapsed_ms,
                explanation=f"Plan executed without step errors, but goal condition '{first_unmet}' was not reached.",
            )

        # Plan completely verified
        return VerificationResultSchema(
            is_valid=True,
            failed_step_index=None,
            failed_action=None,
            violated_condition=None,
            violation_type=ViolationType.NONE,
            post_state=current_state.to_schema(),
            trace=trace,
            verification_time_ms=elapsed_ms,
            explanation="Plan fully verified: all preconditions, invariants, hard constraints, and goals satisfied.",
        )
