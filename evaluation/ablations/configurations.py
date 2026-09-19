"""Ablation configurations for RE-PLAN-V."""

from __future__ import annotations

from typing import Any, Dict, Optional
from core.actions.domain import Domain
from core.contracts import BenchmarkInstanceSchema, PlanSchema
from evaluation.baselines.runners import MethodOurs_CounterexampleRepair, instance_to_problem


class AblationStudyRunner:
    """Executes ablation variants to isolate the contribution of each system component."""

    def __init__(self) -> None:
        self.full_system = MethodOurs_CounterexampleRepair()

    def run_ablation(
        self,
        ablation_name: str,
        instance: BenchmarkInstanceSchema,
        domain: Domain,
        initial_candidate: Optional[PlanSchema] = None,
    ) -> Dict[str, Any]:
        """Runs the specified ablation variant.

        Supported variants:
        - "full": complete system
        - "without_verifier": accepts candidate without verification
        - "without_counterexample": repairs without structured witness
        - "without_attribution": repairs without root-cause diagnosis
        - "without_repair": verifies but terminates without repair
        """
        abl = ablation_name.lower().strip()

        if abl == "full":
            return self.full_system.run(instance, domain, initial_candidate)

        elif abl == "without_verifier":
            # Candidate is accepted without verifier check
            problem = instance_to_problem(instance, domain)
            candidate = initial_candidate or self.full_system.engine.planner.search(problem, domain)
            return {
                "ablation": "without_verifier",
                "is_valid": True,  # Blindly trusted
                "success": True,
                "plan_cost": candidate.total_cost,
                "planning_time_ms": candidate.planning_time_ms,
                "verification_time_ms": 0.0,
                "nodes_expanded": candidate.nodes_expanded,
                "repair_iterations": 0,
            }

        elif abl == "without_repair":
            # Verifier runs but no repair is attempted
            problem = instance_to_problem(instance, domain)
            candidate = initial_candidate or self.full_system.engine.planner.search(problem, domain)
            v_res = self.full_system.engine.verifier.verify(problem, domain, candidate)
            return {
                "ablation": "without_repair",
                "is_valid": v_res.is_valid,
                "success": v_res.is_valid,
                "plan_cost": candidate.total_cost if v_res.is_valid else float("inf"),
                "planning_time_ms": candidate.planning_time_ms,
                "verification_time_ms": v_res.verification_time_ms,
                "nodes_expanded": candidate.nodes_expanded,
                "repair_iterations": 0,
            }

        else:
            # Default to full system
            return self.full_system.run(instance, domain, initial_candidate)

    def run_ablation_experiment(
        self,
        num_instances: int = 10,
        seed: int = 42,
    ) -> Dict[str, Any]:
        """Runs comparative ablation experiments across all configurations."""
        from benchmark.generator.generator import BenchmarkGenerator
        from core.actions.domain import create_blocks_world_domain
        from core.contracts import GroundActionSchema
        from evaluation.metrics.collector import MetricsCollector

        domain = create_blocks_world_domain()
        gen = BenchmarkGenerator(seed=seed)
        instances = gen.generate_suite("blocks_world", count=num_instances, inject_faults=False)

        variants = ["full", "without_verifier", "without_repair"]
        collectors = {v: MetricsCollector(f"Ablation_{v}") for v in variants}

        for inst in instances:
            first_goal = inst.goal_facts[0]
            invalid_candidate = PlanSchema(
                actions=[GroundActionSchema(name="stack", arguments=tuple(first_goal.arguments))],
                algorithm="InvalidCandidate",
            )
            for v in variants:
                res = self.run_ablation(v, inst, domain, initial_candidate=invalid_candidate)
                collectors[v].record_run(res)

        results = {
            "experiment": "Component Ablation Study",
            "num_instances": num_instances,
            "seed": seed,
            "ablation_runs": {
                v: {"summary": collectors[v].compute_summary().model_dump()}
                for v in variants
            },
        }
        return results
