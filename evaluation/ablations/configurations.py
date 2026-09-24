"""Ablation configurations for RE-PLAN-V.

Implements all 6 required ablation variants from Master Specification Section 22:
1. FULL SYSTEM: Planner + Verifier + Counterexample + Fault Attribution + Repair Loop
2. NO VERIFIER: Blindly accepts candidate plans without independent verification
3. NO COUNTEREXAMPLE: Verifies plan, but has no structured minimal witness to guide repair
4. NO FAULT ATTRIBUTION: Bypasses fault diagnosis (assigns UNKNOWN_AMBIGUOUS uniformly)
5. NO REPAIR: Verifies plan and catches errors, but performs no repair or replanning
6. GENERIC REGENERATION: Baseline B3 (blind unguided regeneration without constraints)
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional
from unittest.mock import MagicMock

from core.actions.domain import Domain
from core.contracts import (
    BenchmarkInstanceSchema,
    FaultAttributionSchema,
    FaultClass,
    PlanSchema,
)
from core.replanning.loop import ReplanningEngine
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
        - "full": complete system (OURS)
        - "without_verifier": accepts candidate without verification
        - "without_counterexample": repairs without structured witness
        - "without_attribution": repairs without root-cause diagnosis
        - "without_repair": verifies but terminates without repair
        - "generic_regeneration": blind replanning without repair constraints
        """
        abl = ablation_name.lower().strip()

        # 1. Full system
        if abl == "full":
            res = self.full_system.run(instance, domain, initial_candidate)
            res["ablation"] = "full"
            return res

        # 2. Without verifier (blind acceptance)
        elif abl == "without_verifier":
            problem = instance_to_problem(instance, domain)
            candidate = initial_candidate or self.full_system.engine.planner.search(problem, domain)
            return {
                "ablation": "without_verifier",
                "is_valid": True,  # Blindly trusted without formal verification
                "success": True,
                "plan_cost": candidate.total_cost,
                "planning_time_ms": candidate.planning_time_ms,
                "verification_time_ms": 0.0,
                "nodes_expanded": candidate.nodes_expanded,
                "repair_iterations": 0,
            }

        # 3. Without repair (verifier catches error, but no repair is attempted)
        elif abl == "without_repair":
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
                "final_verification": v_res,
            }

        # 4. Without counterexample (no structured witness extracted; cannot target specific transition)
        elif abl == "without_counterexample":
            problem = instance_to_problem(instance, domain)
            start = time.perf_counter()
            engine_no_cex = ReplanningEngine()
            # Disable counterexample extraction: generator returns None
            engine_no_cex.cex_generator.generate = MagicMock(return_value=None)
            replan_res = engine_no_cex.run_repair_loop(
                problem=problem,
                domain=domain,
                initial_candidate=initial_candidate,
            )
            elapsed = (time.perf_counter() - start) * 1000.0
            return {
                "ablation": "without_counterexample",
                "is_valid": replan_res.success,
                "success": replan_res.success,
                "plan_cost": replan_res.repaired_plan.total_cost if replan_res.repaired_plan and replan_res.success else float("inf"),
                "planning_time_ms": replan_res.replanning_time_ms,
                "verification_time_ms": replan_res.final_verification.verification_time_ms if replan_res.final_verification else 0.0,
                "nodes_expanded": replan_res.repaired_plan.nodes_expanded if replan_res.repaired_plan else 0,
                "repair_iterations": replan_res.iterations,
                "final_verification": replan_res.final_verification,
            }

        # 5. Without attribution (attribution engine bypassed, always UNKNOWN_AMBIGUOUS)
        elif abl == "without_attribution":
            problem = instance_to_problem(instance, domain)
            start = time.perf_counter()
            engine_no_attr = ReplanningEngine()
            # Force attribution to UNKNOWN_AMBIGUOUS without root-cause reasoning
            dummy_attr = FaultAttributionSchema(
                fault_class=FaultClass.UNKNOWN_AMBIGUOUS,
                affected_stage="unknown",
                confidence=0.0,
                explanation="Ablated attribution engine: diagnosis bypassed.",
            )
            engine_no_attr.attribution_engine.attribute = MagicMock(return_value=dummy_attr)
            replan_res = engine_no_attr.run_repair_loop(
                problem=problem,
                domain=domain,
                initial_candidate=initial_candidate,
            )
            elapsed = (time.perf_counter() - start) * 1000.0
            return {
                "ablation": "without_attribution",
                "is_valid": replan_res.success,
                "success": replan_res.success,
                "plan_cost": replan_res.repaired_plan.total_cost if replan_res.repaired_plan and replan_res.success else float("inf"),
                "planning_time_ms": replan_res.replanning_time_ms,
                "verification_time_ms": replan_res.final_verification.verification_time_ms if replan_res.final_verification else 0.0,
                "nodes_expanded": replan_res.repaired_plan.nodes_expanded if replan_res.repaired_plan else 0,
                "repair_iterations": replan_res.iterations,
                "final_verification": replan_res.final_verification,
            }

        # 6. Generic regeneration (Baseline B3: blind regeneration without constraints)
        elif abl in ("generic_regeneration", "without_guided_repair"):
            problem = instance_to_problem(instance, domain)
            candidate = initial_candidate or self.full_system.engine.planner.search(problem, domain)
            res = self.full_system.engine.run_generic_regeneration_baseline(
                problem=problem,
                domain=domain,
                initial_candidate=candidate,
            )
            return {
                "ablation": "generic_regeneration",
                "is_valid": res.success,
                "success": res.success,
                "plan_cost": res.repaired_plan.total_cost if res.repaired_plan and res.success else float("inf"),
                "planning_time_ms": res.replanning_time_ms,
                "verification_time_ms": res.final_verification.verification_time_ms if res.final_verification else 0.0,
                "nodes_expanded": res.repaired_plan.nodes_expanded if res.repaired_plan else 0,
                "repair_iterations": res.iterations,
                "final_verification": res.final_verification,
            }

        else:
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

        variants = [
            "full",
            "without_verifier",
            "without_counterexample",
            "without_attribution",
            "without_repair",
            "generic_regeneration",
        ]
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
