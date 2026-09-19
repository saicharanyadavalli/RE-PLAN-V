"""Structured counterexample generator and failure witness."""

from __future__ import annotations

import uuid
from typing import List, Optional, Set
from core.contracts import (
    CounterexampleSchema,
    FactSchema,
    GroundActionSchema,
    SymbolicStateSchema,
    VerificationResultSchema,
    ViolationType,
)
from core.world.problem import SymbolicProblem


class CounterexampleGenerator:
    """Extracts formal, machine-readable counterexample witness from verification failure."""

    def generate(
        self,
        verification_result: VerificationResultSchema,
        problem: Optional[SymbolicProblem] = None,
        counterexample_id: Optional[str] = None,
    ) -> Optional[CounterexampleSchema]:
        """Generates a structured witness if plan is invalid; returns None if plan is valid."""
        if verification_result.is_valid:
            return None

        cex_id = counterexample_id or f"CEX-{uuid.uuid4().hex[:8].upper()}"
        step_idx = verification_result.failed_step_index if verification_result.failed_step_index is not None else 0

        # Offending action (or placeholder for goal failure)
        offending_action = verification_result.failed_action or GroundActionSchema(
            name="CHECK_GOAL", arguments=(), cost=0.0
        )

        # Violated condition
        violated_cond = verification_result.violated_condition or FactSchema(
            predicate="GOAL_SATISFIED", arguments=(), is_negated=False
        )

        # Affected entities
        affected_set: Set[str] = set()
        affected_set.update(offending_action.arguments)
        affected_set.update(violated_cond.arguments)
        affected_entities = sorted(list(affected_set))

        # State snapshot at failure point
        state_snapshot = verification_result.pre_state or (
            problem.initial_state.to_schema() if problem else SymbolicStateSchema()
        )

        # Determine expected vs actual truth
        expected_truth = True
        actual_truth = False
        if violated_cond.is_negated:
            expected_truth = False
            actual_truth = True

        # Build comprehensive explanatory diagnosis
        v_type = verification_result.violation_type
        if v_type == ViolationType.PRECONDITION_UNMET:
            diagnosis = (
                f"Action '{offending_action.to_string()}' failed at step {step_idx} because precondition "
                f"'{violated_cond.to_string()}' was not satisfied in the state immediately prior to execution."
            )
        elif v_type == ViolationType.INVARIANT_VIOLATED:
            diagnosis = (
                f"Executing action '{offending_action.to_string()}' at step {step_idx} caused a transition into an "
                f"unsafe state violating invariant condition '{violated_cond.to_string()}'."
            )
        elif v_type == ViolationType.HARD_CONSTRAINT_VIOLATED:
            diagnosis = (
                f"Action '{offending_action.to_string()}' at step {step_idx} is prohibited by hard safety constraints "
                f"protecting entities: {affected_entities}."
            )
        elif v_type == ViolationType.GOAL_UNMET:
            diagnosis = (
                f"Plan reached end of execution without step errors, but final state failed to achieve "
                f"goal condition '{violated_cond.to_string()}'."
            )
        else:
            diagnosis = verification_result.explanation or f"Plan execution failed with {v_type} at step {step_idx}."

        trace_summary = f"{len(verification_result.trace)} execution steps recorded; failed at step {step_idx}."

        return CounterexampleSchema(
            counterexample_id=cex_id,
            action_index=step_idx,
            offending_action=offending_action,
            violated_condition=violated_cond,
            expected_truth=expected_truth,
            actual_truth=actual_truth,
            failure_category=v_type,
            affected_entities=affected_entities,
            state_snapshot=state_snapshot,
            trace_summary=trace_summary,
            explanation=diagnosis,
        )
