"""Benchmark baseline implementations: B0, B1, B2, B3, and OURS."""

from __future__ import annotations

import time
from typing import Any, Dict, Optional, Tuple
from core.actions.domain import Domain
from core.attribution.classifier import FaultAttributionEngine
from core.contracts import (
    BenchmarkInstanceSchema,
    GroundActionSchema,
    PlanSchema,
    ReplanningResultSchema,
    VerificationResultSchema,
    ViolationType,
)
from core.counterexamples.generator import CounterexampleGenerator
from core.repair.generator import RepairGenerator
from core.replanning.loop import ReplanningEngine
from core.search.algorithms import AStarPlanner
from core.verification.verifier import PlanVerifier
from core.world.predicates import Fact
from core.world.problem import SymbolicProblem
from core.world.state import SymbolicState
from core.world.types import ObjectRegistry


def instance_to_problem(instance: BenchmarkInstanceSchema, domain: Domain) -> SymbolicProblem:
    reg = ObjectRegistry(domain.type_hierarchy)
    for name, type_name in instance.objects.items():
        reg.register_object(name, type_name)

    init_facts = [Fact.from_schema(f) for f in instance.initial_facts]
    init_state = SymbolicState(facts=init_facts, objects=reg.get_all_objects())
    goals = [Fact.from_schema(g) for g in instance.goal_facts]

    return SymbolicProblem(
        name=instance.name,
        domain_name=instance.domain,
        registry=reg,
        initial_state=init_state,
        goal_conditions=goals,
        description=instance.natural_language_prompt,
    )


# ==============================================================================
# Baseline B0: Direct Neural Plan Generation
# ==============================================================================
class BaselineB0_DirectNeural:
    """Directly proposes action sequence without formal symbolic planner or verifier."""

    def __init__(self, verifier: Optional[PlanVerifier] = None) -> None:
        self.verifier = verifier or PlanVerifier()

    def run(self, instance: BenchmarkInstanceSchema, domain: Domain) -> Dict[str, Any]:
        start = time.perf_counter()
        problem = instance_to_problem(instance, domain)

        # Direct unverified neural heuristic proposal (often misses precondition like pick_up)
        # E.g. simply proposing 'stack' directly for each goal
        proposed_actions = []
        for g in instance.goal_facts:
            if g.predicate == "on" and len(g.arguments) == 2:
                proposed_actions.append(
                    GroundActionSchema(name="stack", arguments=tuple(g.arguments))
                )

        candidate = PlanSchema(
            actions=proposed_actions,
            algorithm="B0_DirectNeural",
            total_cost=float(len(proposed_actions)),
        )

        # Independent verification check for measurement
        v_res = self.verifier.verify(problem, domain, candidate)
        elapsed = (time.perf_counter() - start) * 1000.0

        return {
            "method": "B0_DirectNeural",
            "is_valid": v_res.is_valid,
            "success": v_res.is_valid,
            "plan_cost": candidate.total_cost if v_res.is_valid else float("inf"),
            "planning_time_ms": elapsed,
            "verification_time_ms": v_res.verification_time_ms,
            "nodes_expanded": 0,
            "repair_iterations": 0,
            "final_verification": v_res,
        }


# ==============================================================================
# Baseline B1: Neural Formalization + Classical Planner
# ==============================================================================
class BaselineB1_FormalizedPlanner:
    """Uses formal planner from formal problem, but has no verifier or repair."""

    def __init__(self, planner: Optional[AStarPlanner] = None, verifier: Optional[PlanVerifier] = None) -> None:
        self.planner = planner or AStarPlanner()
        self.verifier = verifier or PlanVerifier()

    def run(self, instance: BenchmarkInstanceSchema, domain: Domain) -> Dict[str, Any]:
        start = time.perf_counter()
        problem = instance_to_problem(instance, domain)

        plan = self.planner.search(problem, domain)
        v_res = self.verifier.verify(problem, domain, plan)
        elapsed = (time.perf_counter() - start) * 1000.0

        return {
            "method": "B1_FormalizedPlanner",
            "is_valid": v_res.is_valid,
            "success": v_res.is_valid,
            "plan_cost": plan.total_cost if v_res.is_valid else float("inf"),
            "planning_time_ms": plan.planning_time_ms,
            "verification_time_ms": v_res.verification_time_ms,
            "nodes_expanded": plan.nodes_expanded,
            "repair_iterations": 0,
            "final_verification": v_res,
        }


# ==============================================================================
# Baseline B2: Planner + Verifier without Repair
# ==============================================================================
class BaselineB2_VerifierNoRepair:
    """Verifies candidate plan, but immediately rejects and terminates upon failure without repair."""

    def __init__(self, planner: Optional[AStarPlanner] = None, verifier: Optional[PlanVerifier] = None) -> None:
        self.planner = planner or AStarPlanner()
        self.verifier = verifier or PlanVerifier()

    def run(
        self,
        instance: BenchmarkInstanceSchema,
        domain: Domain,
        initial_candidate: Optional[PlanSchema] = None,
    ) -> Dict[str, Any]:
        start = time.perf_counter()
        problem = instance_to_problem(instance, domain)

        plan = initial_candidate or self.planner.search(problem, domain)
        v_res = self.verifier.verify(problem, domain, plan)
        elapsed = (time.perf_counter() - start) * 1000.0

        return {
            "method": "B2_VerifierNoRepair",
            "is_valid": v_res.is_valid,
            "success": v_res.is_valid,
            "plan_cost": plan.total_cost if v_res.is_valid else float("inf"),
            "planning_time_ms": elapsed,
            "verification_time_ms": v_res.verification_time_ms,
            "nodes_expanded": plan.nodes_expanded,
            "repair_iterations": 0,
            "final_verification": v_res,
        }


# ==============================================================================
# Baseline B3: Planner + Generic Regeneration
# ==============================================================================
class BaselineB3_GenericRegeneration:
    """When plan is invalid, retries by re-running search without counterexample guidance."""

    def __init__(self, engine: Optional[ReplanningEngine] = None) -> None:
        self.engine = engine or ReplanningEngine()

    def run(
        self,
        instance: BenchmarkInstanceSchema,
        domain: Domain,
        initial_candidate: Optional[PlanSchema] = None,
        max_attempts: int = 3,
    ) -> Dict[str, Any]:
        problem = instance_to_problem(instance, domain)
        candidate = initial_candidate or self.engine.planner.search(problem, domain)

        res = self.engine.run_generic_regeneration_baseline(
            problem=problem,
            domain=domain,
            initial_candidate=candidate,
            max_attempts=max_attempts,
        )

        return {
            "method": "B3_GenericRegeneration",
            "is_valid": res.success,
            "success": res.success,
            "plan_cost": res.repaired_plan.total_cost if res.repaired_plan and res.success else float("inf"),
            "planning_time_ms": res.replanning_time_ms,
            "verification_time_ms": res.final_verification.verification_time_ms if res.final_verification else 0.0,
            "nodes_expanded": res.repaired_plan.nodes_expanded if res.repaired_plan else 0,
            "repair_iterations": res.iterations,
            "final_verification": res.final_verification,
        }


# ==============================================================================
# Method OURS: Full RE-PLAN-V System
# ==============================================================================
class MethodOurs_CounterexampleRepair:
    """Planner + Verifier + Counterexample + Fault Attribution + Repair Loop."""

    def __init__(self, engine: Optional[ReplanningEngine] = None) -> None:
        self.engine = engine or ReplanningEngine()

    def run(
        self,
        instance: BenchmarkInstanceSchema,
        domain: Domain,
        initial_candidate: Optional[PlanSchema] = None,
    ) -> Dict[str, Any]:
        problem = instance_to_problem(instance, domain)
        res = self.engine.run_repair_loop(
            problem=problem,
            domain=domain,
            initial_candidate=initial_candidate,
            natural_language_prompt=instance.natural_language_prompt,
        )

        return {
            "method": "OURS_CounterexampleRepair",
            "is_valid": res.success,
            "success": res.success,
            "plan_cost": res.repaired_plan.total_cost if res.repaired_plan and res.success else float("inf"),
            "planning_time_ms": res.replanning_time_ms,
            "verification_time_ms": res.final_verification.verification_time_ms if res.final_verification else 0.0,
            "nodes_expanded": res.repaired_plan.nodes_expanded if res.repaired_plan else 0,
            "repair_iterations": res.iterations,
            "final_verification": res.final_verification,
            "repairs_applied": res.repairs_applied,
        }
