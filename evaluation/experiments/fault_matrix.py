"""Dedicated 5-Class Fault Attribution & Confusion Matrix Experiment Runner.

Evaluates FaultAttributionEngine on controlled ground-truth injected faults across all 5 classes:
1. PLANNING_ERROR
2. PERCEPTION_ERROR
3. FORMALIZATION_ERROR
4. ENVIRONMENT_CHANGE
5. UNKNOWN_AMBIGUOUS
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Ensure project root is on sys.path
root_dir = Path(__file__).resolve().parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from core.actions.domain import create_blocks_world_domain
from core.attribution.classifier import FaultAttributionEngine
from core.attribution.mutation import FaultInjector
from core.contracts import (
    CounterexampleSchema,
    FactSchema,
    FaultClass,
    GroundActionSchema,
    PlanSchema,
    SymbolicStateSchema,
    ViolationType,
    WorldDeltaSchema,
)
from core.counterexamples.generator import CounterexampleGenerator
from core.verification.verifier import PlanVerifier
from core.world.predicates import Fact
from core.world.problem import SymbolicProblem
from core.world.state import SymbolicState
from core.world.types import ObjectRegistry


class AttributionMatrixExperiment:
    """Evaluates attribution accuracy, per-class precision/recall/F1, and confusion matrix."""

    def __init__(self, output_dir: Path | None = None) -> None:
        self.output_dir = output_dir or Path(__file__).resolve().parent.parent / "reports"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.engine = FaultAttributionEngine()
        self.classes = [
            FaultClass.PLANNING_ERROR,
            FaultClass.PERCEPTION_ERROR,
            FaultClass.FORMALIZATION_ERROR,
            FaultClass.ENVIRONMENT_CHANGE,
            FaultClass.UNKNOWN_AMBIGUOUS,
        ]

    def _create_sample_problem(self, suffix: str = "") -> Tuple[SymbolicProblem, Any]:
        domain = create_blocks_world_domain()
        reg = ObjectRegistry(domain.type_hierarchy)
        reg.register_object(f"b1{suffix}", "block")
        reg.register_object(f"b2{suffix}", "block")
        reg.register_object(f"b3{suffix}", "block")

        init_facts = [
            Fact("on_table", [f"b1{suffix}"]),
            Fact("clear", [f"b1{suffix}"]),
            Fact("on_table", [f"b2{suffix}"]),
            Fact("clear", [f"b2{suffix}"]),
            Fact("on_table", [f"b3{suffix}"]),
            Fact("clear", [f"b3{suffix}"]),
            Fact("handempty", []),
        ]
        s0 = SymbolicState(facts=init_facts, objects=reg.get_all_objects())
        problem = SymbolicProblem(
            name=f"AttrProblem{suffix}",
            domain_name=domain.name,
            registry=reg,
            initial_state=s0,
            goal_conditions=[Fact("on", [f"b1{suffix}", f"b2{suffix}"])],
        )
        return problem, domain

    def _generate_test_case(self, fault_class: FaultClass, idx: int) -> Dict[str, Any]:
        suffix = f"_{fault_class.value[:3]}_{idx}"
        problem, domain = self._create_sample_problem(suffix)
        b1, b2, b3 = f"b1{suffix}", f"b2{suffix}", f"b3{suffix}"

        if fault_class == FaultClass.PLANNING_ERROR:
            broken_plan = [GroundActionSchema(name="stack", arguments=(b1, b2))]
            verifier = PlanVerifier()
            v_res = verifier.verify(problem, domain, broken_plan)
            cex = CounterexampleGenerator().generate(v_res, problem)
            return {
                "ground_truth": FaultClass.PLANNING_ERROR,
                "counterexample": cex,
                "problem": problem,
            }

        elif fault_class == FaultClass.PERCEPTION_ERROR:
            cex = CounterexampleSchema(
                counterexample_id=f"CEX-PERC-{idx}",
                action_index=0,
                offending_action=GroundActionSchema(name="pick_up", arguments=(b1,)),
                violated_condition=FactSchema(predicate="clear", arguments=(b1,)),
                expected_truth=True,
                actual_truth=False,
                failure_category=ViolationType.PRECONDITION_UNMET,
                affected_entities=[b1],
                state_snapshot=SymbolicStateSchema(),
            )
            observed = [FactSchema(predicate="clear", arguments=(b1,))]
            ground_truth = [FactSchema(predicate="on", arguments=(b2, b1))]
            return {
                "ground_truth": FaultClass.PERCEPTION_ERROR,
                "counterexample": cex,
                "observed_facts": observed,
                "ground_truth_facts": ground_truth,
            }

        elif fault_class == FaultClass.FORMALIZATION_ERROR:
            prompt = f"Stack {b1} on {b2}. Do not move {b3}."
            cex = CounterexampleSchema(
                counterexample_id=f"CEX-FORM-{idx}",
                action_index=0,
                offending_action=GroundActionSchema(name="pick_up", arguments=(b3,)),
                violated_condition=FactSchema(predicate="holding", arguments=(b3,)),
                expected_truth=False,
                actual_truth=True,
                failure_category=ViolationType.PRECONDITION_UNMET,
                affected_entities=[b3],
                state_snapshot=problem.initial_state.to_schema(),
            )
            return {
                "ground_truth": FaultClass.FORMALIZATION_ERROR,
                "counterexample": cex,
                "problem": problem,
                "natural_language_prompt": prompt,
            }

        elif fault_class == FaultClass.ENVIRONMENT_CHANGE:
            cex = CounterexampleSchema(
                counterexample_id=f"CEX-ENV-{idx}",
                action_index=1,
                offending_action=GroundActionSchema(name="pick_up", arguments=(b1,)),
                violated_condition=FactSchema(predicate="clear", arguments=(b1,)),
                expected_truth=True,
                actual_truth=False,
                failure_category=ViolationType.PRECONDITION_UNMET,
                affected_entities=[b1],
                state_snapshot=SymbolicStateSchema(),
            )
            delta = WorldDeltaSchema(
                delta_id=f"DELTA-{idx}",
                added_facts=[FactSchema(predicate="on", arguments=(b3, b1))],
                removed_facts=[FactSchema(predicate="clear", arguments=(b1,))],
                affected_entities=[b1],
                is_plan_invalidating=True,
            )
            return {
                "ground_truth": FaultClass.ENVIRONMENT_CHANGE,
                "counterexample": cex,
                "environment_deltas": [delta],
            }

        else:  # UNKNOWN_AMBIGUOUS
            cex = CounterexampleSchema(
                counterexample_id=f"CEX-UNK-{idx}",
                action_index=0,
                offending_action=GroundActionSchema(name="noop", arguments=()),
                violated_condition=FactSchema(predicate="undefined_condition", arguments=()),
                expected_truth=True,
                actual_truth=False,
                failure_category=ViolationType.NONE,
                affected_entities=[],
                state_snapshot=SymbolicStateSchema(),
            )
            return {
                "ground_truth": FaultClass.UNKNOWN_AMBIGUOUS,
                "counterexample": cex,
            }

    def run_evaluation(self, instances_per_class: int = 5, seed: int = 42) -> Dict[str, Any]:
        """Runs the attribution matrix evaluation across all 5 classes."""
        class_names = [c.value for c in self.classes]
        matrix: Dict[str, Dict[str, int]] = {
            gt: {pred: 0 for pred in class_names} for gt in class_names
        }

        total = 0
        correct = 0

        for fault_cls in self.classes:
            for idx in range(instances_per_class):
                case = self._generate_test_case(fault_cls, idx)
                gt_label = case["ground_truth"].value

                # Note: Ground truth label is strictly withheld from the attribution call
                attr = self.engine.attribute(
                    counterexample=case["counterexample"],
                    problem=case.get("problem"),
                    natural_language_prompt=case.get("natural_language_prompt"),
                    observed_facts=case.get("observed_facts"),
                    ground_truth_facts=case.get("ground_truth_facts"),
                    environment_deltas=case.get("environment_deltas"),
                )
                pred_label = attr.fault_class.value

                matrix[gt_label][pred_label] += 1
                total += 1
                if gt_label == pred_label:
                    correct += 1

        accuracy = correct / max(1, total)

        per_class: Dict[str, Dict[str, float]] = {}
        for c in class_names:
            tp = matrix[c][c]
            fp = sum(matrix[other][c] for other in class_names if other != c)
            fn = sum(matrix[c][other] for other in class_names if other != c)

            prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0

            per_class[c] = {
                "precision": round(prec, 4),
                "recall": round(rec, 4),
                "f1_score": round(f1, 4),
                "support": tp + fn,
            }

        macro_prec = sum(p["precision"] for p in per_class.values()) / len(class_names)
        macro_rec = sum(p["recall"] for p in per_class.values()) / len(class_names)
        macro_f1 = sum(p["f1_score"] for p in per_class.values()) / len(class_names)

        results = {
            "experiment": "5-Class Fault Attribution Matrix & Precision-Recall Analysis",
            "total_evaluated": total,
            "accuracy": round(accuracy, 4),
            "macro_precision": round(macro_prec, 4),
            "macro_recall": round(macro_rec, 4),
            "macro_f1": round(macro_f1, 4),
            "per_class": per_class,
            "confusion_matrix": matrix,
        }

        report_file = self.output_dir / "fault_attribution_matrix.json"
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)

        return results


if __name__ == "__main__":
    exp = AttributionMatrixExperiment()
    res = exp.run_evaluation(instances_per_class=10, seed=42)
    print(json.dumps(res, indent=2))
