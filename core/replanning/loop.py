"""Iterative counterexample-guided repair and replanning loop."""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Set, Tuple

from core.actions.domain import Domain
from core.actions.instantiation import GroundAction
from core.attribution.classifier import FaultAttributionEngine
from core.contracts import (
    PlanSchema,
    RepairConstraintSchema,
    ReplanningResultSchema,
    VerificationResultSchema,
)
from core.counterexamples.generator import CounterexampleGenerator
from core.repair.generator import RepairGenerator
from core.repair.models import RepairConstraint
from core.search.algorithms import AStarPlanner, BasePlanner, get_planner_by_name
from core.verification.verifier import PlanVerifier
from core.world.problem import SymbolicProblem
from core.world.state import SymbolicState


class ReplanningEngine:
    """Orchestrates the counterexample-guided repair and replanning loop."""

    def __init__(
        self,
        planner: Optional[BasePlanner] = None,
        verifier: Optional[PlanVerifier] = None,
        max_repair_iterations: int = 5,
    ) -> None:
        self.planner = planner or AStarPlanner()
        self.verifier = verifier or PlanVerifier()
        self.cex_generator = CounterexampleGenerator()
        self.attribution_engine = FaultAttributionEngine()
        self.repair_generator = RepairGenerator()
        self.max_repair_iterations = max_repair_iterations

    def run_repair_loop(
        self,
        problem: SymbolicProblem,
        domain: Domain,
        initial_candidate: Optional[PlanSchema] = None,
        natural_language_prompt: Optional[str] = None,
    ) -> ReplanningResultSchema:
        """Executes Candidate -> Verify -> Counterexample -> Attribution -> Repair -> Replan -> Verify."""
        start_time = time.perf_counter()

        # Step 1: Obtain or generate initial candidate plan
        if initial_candidate is None:
            current_candidate = self.planner.search(problem, domain)
        else:
            current_candidate = initial_candidate

        original_plan = current_candidate
        accumulated_repairs: List[RepairConstraint] = []
        forbidden_ground_actions: Set[GroundAction] = set()
        seen_counterexamples: Set[str] = set()
        history: List[Dict[str, Any]] = []

        current_problem = problem

        for iteration in range(self.max_repair_iterations + 1):
            # Step 2: Verification
            v_res: VerificationResultSchema = self.verifier.verify(current_problem, domain, current_candidate)

            history.append({
                "iteration": iteration,
                "plan_length": len(current_candidate.actions),
                "is_valid": v_res.is_valid,
                "violation_type": v_res.violation_type.value,
                "failed_step": v_res.failed_step_index,
                "explanation": v_res.explanation,
            })

            # Check if verified
            if v_res.is_valid:
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                return ReplanningResultSchema(
                    success=True,
                    original_plan=original_plan,
                    repaired_plan=current_candidate,
                    iterations=iteration,
                    repairs_applied=[r.to_schema() for r in accumulated_repairs],
                    final_verification=v_res,
                    replanning_time_ms=elapsed_ms,
                    status="VERIFIED",
                    history=history,
                )

            # Check iteration limit
            if iteration >= self.max_repair_iterations:
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                return ReplanningResultSchema(
                    success=False,
                    original_plan=original_plan,
                    repaired_plan=current_candidate,
                    iterations=iteration,
                    repairs_applied=[r.to_schema() for r in accumulated_repairs],
                    final_verification=v_res,
                    replanning_time_ms=elapsed_ms,
                    status="MAX_ITERATIONS_REACHED",
                    history=history,
                )

            # Step 3: Counterexample generation
            cex = self.cex_generator.generate(v_res, current_problem)
            if cex is None:
                break

            # Loop detection guard
            cex_signature = f"{cex.action_index}:{cex.offending_action.to_string()}:{cex.violated_condition.to_string()}"
            if cex_signature in seen_counterexamples:
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                return ReplanningResultSchema(
                    success=False,
                    original_plan=original_plan,
                    repaired_plan=current_candidate,
                    iterations=iteration,
                    repairs_applied=[r.to_schema() for r in accumulated_repairs],
                    final_verification=v_res,
                    replanning_time_ms=elapsed_ms,
                    status="LOOP_DETECTED",
                    history=history,
                )
            seen_counterexamples.add(cex_signature)

            # Step 4: Fault attribution
            attribution = self.attribution_engine.attribute(
                counterexample=cex,
                problem=current_problem,
                candidate_plan=current_candidate,
                natural_language_prompt=natural_language_prompt,
            )

            # Step 5: Repair generation
            repair = self.repair_generator.generate(cex, attribution, current_problem, domain)
            accumulated_repairs.append(repair)

            if repair.forbidden_action and not repair.forbidden_state_facts:
                forbidden_ground_actions.add(repair.forbidden_action)

            # State belief correction if applicable
            if repair.state_corrections_add or repair.state_corrections_del:
                corrected_state = current_problem.initial_state.apply_effects(
                    adds=repair.state_corrections_add,
                    dels=repair.state_corrections_del,
                )
                current_problem = SymbolicProblem(
                    name=f"{current_problem.name}_corrected",
                    domain_name=current_problem.domain_name,
                    registry=current_problem.registry,
                    initial_state=corrected_state,
                    goal_conditions=current_problem.goal_conditions,
                    invariants=current_problem.invariants,
                    hard_constraints=current_problem.hard_constraints,
                )

            # Step 6: Replanning with repair pruning callback
            def prune_callback(st: SymbolicState, act: GroundAction) -> bool:
                return any(rep.prunes_transition(st, act) for rep in accumulated_repairs)

            new_plan = self.planner.search(
                problem=current_problem,
                domain=domain,
                forbidden_actions=forbidden_ground_actions,
                prune_action_callback=prune_callback,
            )

            if not new_plan.is_success:
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                return ReplanningResultSchema(
                    success=False,
                    original_plan=original_plan,
                    repaired_plan=None,
                    iterations=iteration + 1,
                    repairs_applied=[r.to_schema() for r in accumulated_repairs],
                    final_verification=v_res,
                    replanning_time_ms=elapsed_ms,
                    status="NO_VERIFIED_PLAN",
                    history=history,
                )

            current_candidate = new_plan

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        return ReplanningResultSchema(
            success=False,
            original_plan=original_plan,
            repaired_plan=None,
            iterations=self.max_repair_iterations,
            repairs_applied=[r.to_schema() for r in accumulated_repairs],
            final_verification=None,
            replanning_time_ms=elapsed_ms,
            status="NO_VERIFIED_PLAN",
            history=history,
        )

    def run_generic_regeneration_baseline(
        self,
        problem: SymbolicProblem,
        domain: Domain,
        initial_candidate: PlanSchema,
        max_attempts: int = 5,
    ) -> ReplanningResultSchema:
        """Baseline B3: Generic unguided regeneration without counterexample repair constraints."""
        start_time = time.perf_counter()
        current_candidate = initial_candidate
        history: List[Dict[str, Any]] = []

        for attempt in range(max_attempts + 1):
            v_res = self.verifier.verify(problem, domain, current_candidate)
            history.append({
                "attempt": attempt,
                "is_valid": v_res.is_valid,
                "violation_type": v_res.violation_type.value,
            })
            if v_res.is_valid:
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                return ReplanningResultSchema(
                    success=True,
                    original_plan=initial_candidate,
                    repaired_plan=current_candidate,
                    iterations=attempt,
                    repairs_applied=[],
                    final_verification=v_res,
                    replanning_time_ms=elapsed_ms,
                    status="VERIFIED",
                    history=history,
                )

            if attempt >= max_attempts:
                break

            # Blind regeneration: re-run search without any counterexample constraints
            # (In standard planners, this yields the same deterministic candidate or fails to recover)
            new_candidate = self.planner.search(problem, domain)
            current_candidate = new_candidate

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        return ReplanningResultSchema(
            success=False,
            original_plan=initial_candidate,
            repaired_plan=current_candidate,
            iterations=max_attempts,
            repairs_applied=[],
            final_verification=v_res,
            replanning_time_ms=elapsed_ms,
            status="REGENERATION_FAILED",
            history=history,
        )
