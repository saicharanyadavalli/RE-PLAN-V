"""Evaluation metrics collector and aggregator."""

from __future__ import annotations

from typing import Any, Dict, List
from core.contracts import EvaluationMetricsSchema


class MetricsCollector:
    """Computes strictly measured empirical metrics across benchmark executions."""

    def __init__(self, experiment_id: str = "exp_01") -> None:
        self.experiment_id = experiment_id
        self.records: List[Dict[str, Any]] = []

    def record_run(self, result: Dict[str, Any]) -> None:
        self.records.append(result)

    def compute_summary(self) -> EvaluationMetricsSchema:
        if not self.records:
            return EvaluationMetricsSchema(experiment_id=self.experiment_id)

        n = len(self.records)
        valid_count = sum(1 for r in self.records if r.get("is_valid", False))
        success_count = sum(1 for r in self.records if r.get("success", False))

        # Denominator for repair success rate is N_initially_invalid
        invalid_cases = [r for r in self.records if r.get("initial_plan_was_invalid", False)]
        if invalid_cases:
            repair_success = sum(1 for r in invalid_cases if r.get("success", False))
            repair_rate = float(repair_success / len(invalid_cases))
        else:
            # If no invalid plans were provided, rate matches overall validity
            repair_rate = float(valid_count / n)

        total_iterations = sum(r.get("repair_iterations", 0) for r in self.records)
        total_plan_time = sum(r.get("planning_time_ms", 0.0) for r in self.records)
        total_verif_time = sum(r.get("verification_time_ms", 0.0) for r in self.records)
        
        # Dedicated isolated timer for repair time
        repair_times = [
            r.get("repair_time_ms", 0.0)
            for r in self.records
            if r.get("initial_plan_was_invalid", False) or r.get("repair_iterations", 0) > 0
        ]
        avg_repair_time = (sum(repair_times) / len(repair_times)) if repair_times else 0.0

        total_nodes = sum(r.get("nodes_expanded", 0) for r in self.records)

        finite_costs = [r.get("plan_cost", 0.0) for r in self.records if r.get("plan_cost", float("inf")) < float("inf")]
        avg_cost = sum(finite_costs) / max(1, len(finite_costs)) if finite_costs else 0.0

        # Empirical attribution accuracy
        attr_records = [r for r in self.records if "attribution_correct" in r]
        if attr_records:
            attr_acc = float(sum(1 for r in attr_records if r["attribution_correct"]) / len(attr_records))
        else:
            # Baseline methods that don't do attribution report 0.0
            attr_acc = 0.0

        return EvaluationMetricsSchema(
            experiment_id=self.experiment_id,
            total_instances=n,
            valid_plan_rate=float(valid_count / n),
            goal_success_rate=float(success_count / n),
            constraint_violation_rate=float(1.0 - (valid_count / n)),
            repair_success_rate=repair_rate,
            avg_repair_iterations=float(total_iterations / n),
            avg_planning_time_ms=float(total_plan_time / n),
            avg_verification_time_ms=float(total_verif_time / n),
            avg_repair_time_ms=float(avg_repair_time),
            avg_nodes_expanded=float(total_nodes / n),
            avg_plan_cost=float(avg_cost),
            fault_attribution_accuracy=attr_acc,
            recovery_advantage_over_regeneration=0.0,
        )
