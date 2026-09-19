"""Evidence-guided fault attribution engine.

Taxonomy:
- PERCEPTION_ERROR
- FORMALIZATION_ERROR
- PLANNING_ERROR
- ENVIRONMENT_CHANGE
- UNKNOWN_AMBIGUOUS
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Set
from core.contracts import (
    CounterexampleSchema,
    FactSchema,
    FaultAttributionSchema,
    FaultClass,
    PlanSchema,
    ViolationType,
    WorldDeltaSchema,
)
from core.world.problem import SymbolicProblem


class FaultAttributionEngine:
    """Classifies verification failures into root cause categories grounded in evidence."""

    def attribute(
        self,
        counterexample: CounterexampleSchema,
        problem: Optional[SymbolicProblem] = None,
        candidate_plan: Optional[PlanSchema] = None,
        natural_language_prompt: Optional[str] = None,
        observed_facts: Optional[Sequence[FactSchema]] = None,
        ground_truth_facts: Optional[Sequence[FactSchema]] = None,
        environment_deltas: Optional[Sequence[WorldDeltaSchema]] = None,
    ) -> FaultAttributionSchema:
        evidence: List[str] = []
        alt_hypotheses: List[str] = []

        # 1. Evidence Check: ENVIRONMENT_CHANGE
        # Check if external environment deltas occurred during or prior to the failure
        if environment_deltas:
            for delta in environment_deltas:
                # Check if removed facts match the violated condition
                for rem in delta.removed_facts:
                    if (
                        rem.predicate.lower() == counterexample.violated_condition.predicate.lower()
                        and tuple(rem.arguments) == tuple(counterexample.violated_condition.arguments)
                    ):
                        evidence.append(
                            f"Environment change delta '{delta.delta_id}' removed required condition "
                            f"'{rem.to_string()}' prior to step {counterexample.action_index}."
                        )
                        return FaultAttributionSchema(
                            fault_class=FaultClass.ENVIRONMENT_CHANGE,
                            confidence=0.95,
                            affected_stage="Environment / World Monitor",
                            evidence=evidence,
                            alternative_hypotheses=["Planning error in stale state"],
                            explanation="The failure was caused by an external world modification that invalidated the plan's belief state.",
                        )

        # 2. Evidence Check: PERCEPTION_ERROR
        # Check discrepancy between observed/perceived facts and true symbolic reality
        if observed_facts is not None and ground_truth_facts is not None:
            obs_set = {(f.predicate.lower(), tuple(f.arguments), f.is_negated) for f in observed_facts}
            gt_set = {(f.predicate.lower(), tuple(f.arguments), f.is_negated) for f in ground_truth_facts}

            # Check if the violated condition was falsely believed to hold due to perception
            v_tuple = (
                counterexample.violated_condition.predicate.lower(),
                tuple(counterexample.violated_condition.arguments),
                counterexample.violated_condition.is_negated,
            )

            # Hallucinated fact: in perception but not in ground truth
            if v_tuple in obs_set and v_tuple not in gt_set:
                evidence.append(
                    f"Perception falsely reported '{counterexample.violated_condition.to_string()}' as holding, "
                    f"which does not exist in ground truth environment state."
                )
                return FaultAttributionSchema(
                    fault_class=FaultClass.PERCEPTION_ERROR,
                    confidence=0.90,
                    affected_stage="Perception / Vision",
                    evidence=evidence,
                    alternative_hypotheses=["Formalization error"],
                    explanation="The failure stems from a perceptual error where the vision system reported a false condition.",
                )

            # Missed fact: in ground truth but missed by perception
            if v_tuple not in obs_set and v_tuple in gt_set:
                evidence.append(
                    f"Perception failed to detect condition '{counterexample.violated_condition.to_string()}' "
                    f"which was present in ground truth environment."
                )
                return FaultAttributionSchema(
                    fault_class=FaultClass.PERCEPTION_ERROR,
                    confidence=0.88,
                    affected_stage="Perception / Vision",
                    evidence=evidence,
                    alternative_hypotheses=["Formalization error"],
                    explanation="The failure stems from incomplete visual perception missing a required condition.",
                )

        # 3. Evidence Check: FORMALIZATION_ERROR
        # Check discrepancy between natural language instructions and formal problem specification
        if natural_language_prompt and problem:
            prompt_lower = natural_language_prompt.lower()
            # E.g., user prompt forbade an action or entity, but problem definition omitted hard constraint
            for entity in counterexample.affected_entities:
                if f"do not move {entity.lower()}" in prompt_lower or f"do not touch {entity.lower()}" in prompt_lower:
                    has_constraint = any(
                        entity.lower() in str(c.name).lower() for c in problem.hard_constraints
                    )
                    if not has_constraint:
                        evidence.append(
                            f"User prompt explicitly requested: 'do not move/touch {entity}', but no corresponding "
                            f"hard constraint was registered in the formal SymbolicProblem."
                        )
                        return FaultAttributionSchema(
                            fault_class=FaultClass.FORMALIZATION_ERROR,
                            confidence=0.92,
                            affected_stage="Formalization / Schema Validation",
                            evidence=evidence,
                            alternative_hypotheses=["Planning error"],
                            explanation="Discrepancy between natural-language task requirements and the formal symbolic model.",
                        )

        # 4. Evidence Check: PLANNING_ERROR
        # If problem is sound and failure is due to an invalid action sequence, precondition violation,
        # or invariant violation during plan execution:
        if counterexample.failure_category in (
            ViolationType.PRECONDITION_UNMET,
            ViolationType.INVARIANT_VIOLATED,
            ViolationType.HARD_CONSTRAINT_VIOLATED,
            ViolationType.GOAL_UNMET,
        ):
            evidence.append(
                f"Formal domain semantics and problem specifications are sound; the plan's action sequence "
                f"at step {counterexample.action_index} violated {counterexample.failure_category.value}: "
                f"{counterexample.violated_condition.to_string()}."
            )
            return FaultAttributionSchema(
                fault_class=FaultClass.PLANNING_ERROR,
                confidence=0.85,
                affected_stage="Search / Planner",
                evidence=evidence,
                alternative_hypotheses=["Unknown domain flaw"],
                explanation="The failure was caused by the planning search selecting an invalid or unachievable action sequence.",
            )

        # 5. Fallback: UNKNOWN_AMBIGUOUS
        # Rule 7: If evidence is insufficient, return UNKNOWN/AMBIGUOUS
        return FaultAttributionSchema(
            fault_class=FaultClass.UNKNOWN_AMBIGUOUS,
            confidence=0.30,
            affected_stage="Unknown",
            evidence=["Insufficient evidence to determine whether fault is perception, formalization, or planning."],
            alternative_hypotheses=["PERCEPTION_ERROR", "FORMALIZATION_ERROR", "PLANNING_ERROR"],
            explanation="Failure could not be definitively attributed given available trace evidence.",
        )
