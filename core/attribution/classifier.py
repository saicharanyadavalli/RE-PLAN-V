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
        detected_hypotheses: Dict[FaultClass, Dict[str, Any]] = {}

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
                        detected_hypotheses[FaultClass.ENVIRONMENT_CHANGE] = {
                            "confidence": 0.95,
                            "affected_stage": "Environment / World Monitor",
                            "evidence": [
                                f"Environment change delta '{delta.delta_id}' removed required condition "
                                f"'{rem.to_string()}' prior to step {counterexample.action_index}."
                            ],
                            "explanation": "The failure was caused by an external world modification that invalidated the plan's belief state.",
                        }
                        break

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
                detected_hypotheses[FaultClass.PERCEPTION_ERROR] = {
                    "confidence": 0.90,
                    "affected_stage": "Perception / Vision",
                    "evidence": [
                        f"Perception falsely reported '{counterexample.violated_condition.to_string()}' as holding, "
                        f"which does not exist in ground truth environment state."
                    ],
                    "explanation": "The failure stems from a perceptual error where the vision system reported a false condition.",
                }
            # Missed fact: in ground truth but missed by perception
            elif v_tuple not in obs_set and v_tuple in gt_set:
                detected_hypotheses[FaultClass.PERCEPTION_ERROR] = {
                    "confidence": 0.88,
                    "affected_stage": "Perception / Vision",
                    "evidence": [
                        f"Perception failed to detect condition '{counterexample.violated_condition.to_string()}' "
                        f"which was present in ground truth environment."
                    ],
                    "explanation": "The failure stems from incomplete visual perception missing a required condition.",
                }

        # 3. Evidence Check: FORMALIZATION_ERROR
        # Check discrepancy between natural language instructions and formal problem specification
        if natural_language_prompt and problem:
            prompt_lower = natural_language_prompt.lower()
            for entity in counterexample.affected_entities:
                neg_patterns = [
                    f"do not move {entity.lower()}",
                    f"do not touch {entity.lower()}",
                    f"never move {entity.lower()}",
                    f"avoid {entity.lower()}",
                    f"without touching {entity.lower()}",
                ]
                if any(pat in prompt_lower for pat in neg_patterns):
                    has_constraint = any(
                        entity.lower() in str(c.name).lower() for c in problem.hard_constraints
                    )
                    if not has_constraint:
                        detected_hypotheses[FaultClass.FORMALIZATION_ERROR] = {
                            "confidence": 0.92,
                            "affected_stage": "Formalization / Schema Validation",
                            "evidence": [
                                f"User prompt explicitly requested restriction on '{entity}', but no corresponding "
                                f"hard constraint was registered in the formal SymbolicProblem."
                            ],
                            "explanation": "Discrepancy between natural-language task requirements and the formal symbolic model.",
                        }
                        break

        # Check for multi-cause conflict / ambiguity between strong external/perception/formalization hypotheses
        if len(detected_hypotheses) > 1:
            classes = [c.value for c in detected_hypotheses.keys()]
            evs = [ev for h in detected_hypotheses.values() for ev in h["evidence"]]
            return FaultAttributionSchema(
                fault_class=FaultClass.UNKNOWN_AMBIGUOUS,
                confidence=0.45,
                affected_stage="Ambiguous Multi-Stage Conflict",
                evidence=evs + [f"Conflicting strong evidence supports multiple root causes: {classes}."],
                alternative_hypotheses=classes,
                explanation="Multiple conflicting failure causes detected simultaneously; abstaining from decisive attribution.",
            )

        if len(detected_hypotheses) == 1:
            cls, info = next(iter(detected_hypotheses.items()))
            alts = [c.value for c in [FaultClass.PLANNING_ERROR, FaultClass.UNKNOWN_AMBIGUOUS] if c != cls]
            return FaultAttributionSchema(
                fault_class=cls,
                confidence=info["confidence"],
                affected_stage=info["affected_stage"],
                evidence=info["evidence"],
                alternative_hypotheses=alts,
                explanation=info["explanation"],
            )

        # 4. Evidence Check: PLANNING_ERROR
        # If problem is sound and failure is due to an invalid action sequence, precondition violation,
        # or invariant violation during plan execution:
        if counterexample.failure_category in (
            ViolationType.PRECONDITION_UNMET,
            ViolationType.INVARIANT_VIOLATED,
            ViolationType.HARD_CONSTRAINT_VIOLATED,
            ViolationType.GOAL_UNMET,
        ) and counterexample.violated_condition.predicate != "undefined_condition":
            evidence = [
                f"Formal domain semantics and problem specifications are sound; the plan's action sequence "
                f"at step {counterexample.action_index} violated {counterexample.failure_category.value}: "
                f"{counterexample.violated_condition.to_string()}."
            ]
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
