"""End-to-end pipeline orchestrator for RE-PLAN-V.

Implements a Retry Tree architecture with:
- LLM interpretation retry with error feedback (up to 3 attempts per provider)
- Planner cascade: A* -> BFS -> Best-First
- Backtracking from planning failure -> re-interpretation
- Full decision trace recording
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional
from PIL import Image
from pydantic import BaseModel, Field

from core.actions.domain import Domain, create_blocks_world_domain, create_gridworld_domain
from core.attribution.classifier import FaultAttributionEngine
from core.contracts import (
    CounterexampleSchema,
    FaultAttributionSchema,
    GroundActionSchema,
    PipelineDecisionTrace,
    PipelineStageStatus,
    PlanSchema,
    ProposalValidationResult,
    RepairConstraintSchema,
    ReplanningResultSchema,
    StageAttemptRecord,
    TaskProposalSchema,
    VerificationResultSchema,
    WorldDeltaSchema,
)
from core.counterexamples.generator import CounterexampleGenerator
from core.logger import get_logger
from core.repair.generator import RepairGenerator
from core.replanning.loop import ReplanningEngine
from core.search.algorithms import BasePlanner, get_planner_by_name
from core.verification.verifier import PlanVerifier
from core.world.problem import SymbolicProblem
from interpretation.llm.base import BaseLLMProvider
from interpretation.llm.mock import MockLLMProvider
from interpretation.validator.validator import ConsistencyValidator
from interpretation.vision.detector import DeterministicSceneDetector

logger = get_logger("pipeline")

# Planner cascade order: try A* first (optimal), then BFS (complete), then Best-First (fast)
PLANNER_CASCADE = ["A*", "BFS", "BEST_FIRST"]


class PipelineExecutionResult(BaseModel):
    """Complete, end-to-end trace of a task through the RE-PLAN-V pipeline."""
    task_id: str
    raw_prompt: str
    has_image: bool = False
    interpretation: TaskProposalSchema
    validation: ProposalValidationResult
    symbolic_problem_name: str
    planner_algorithm: str
    candidate_plan: PlanSchema
    initial_verification: VerificationResultSchema
    counterexample: Optional[CounterexampleSchema] = None
    fault_attribution: Optional[FaultAttributionSchema] = None
    repairs_applied: List[RepairConstraintSchema] = Field(default_factory=list)
    replanning_result: Optional[ReplanningResultSchema] = None
    final_plan: Optional[PlanSchema] = None
    final_verification: VerificationResultSchema
    total_execution_time_ms: float = 0.0
    decision_trace: Optional[PipelineDecisionTrace] = None


class PipelineOrchestrator:
    """Coordinates interpretation, validation, planning, verification, attribution, and repair.

    Architecture: Retry Tree with fallback cascading
    ─────────────────────────────────────────────────
    Stage 1: INTERPRET  → retry with error feedback (up to max_interpret_retries)
    Stage 2: VALIDATE   → on fail, re-prompt LLM with validation errors
    Stage 3: PLAN       → cascade through A* → BFS → Best-First
    Stage 4: VERIFY     → if invalid, enter repair loop
    Stage 5: REPAIR     → counterexample-guided repair loop
    Backtrack: PLAN fail or REPAIR fail → re-interpret with different strategy
    """

    def __init__(
        self,
        llm_provider: Optional[BaseLLMProvider] = None,
        validator: Optional[ConsistencyValidator] = None,
        verifier: Optional[PlanVerifier] = None,
        replanning_engine: Optional[ReplanningEngine] = None,
        max_interpret_retries: int = 3,
        max_backtracks: int = 2,
    ) -> None:
        self.domain = create_blocks_world_domain()
        self.llm_provider = llm_provider or MockLLMProvider()
        self.validator = validator or ConsistencyValidator()
        self.verifier = verifier or PlanVerifier()
        self.replanning_engine = replanning_engine or ReplanningEngine(verifier=self.verifier)
        self.cex_generator = CounterexampleGenerator()
        self.attribution_engine = FaultAttributionEngine()
        self.repair_generator = RepairGenerator()
        self.vision_detector = DeterministicSceneDetector()
        self.max_interpret_retries = max_interpret_retries
        self.max_backtracks = max_backtracks

    def run(
        self,
        prompt: str,
        image: Optional[Image.Image] = None,
        algorithm: str = "A*",
        force_invalid_first_candidate: bool = False,
        provider_type: str = "mock",
        llm_model: Optional[str] = None,
    ) -> PipelineExecutionResult:
        """Executes the full Retry Tree pipeline from natural language prompt to verified plan.

        Decision Tree Flow:
            INTERPRET ──► VALIDATE ──► PLAN ──► VERIFY ──► SUCCESS
               ▲    fail     │  fail     │  fail    │  fail
               │    retry    ▼  retry    ▼  cascade ▼  repair
               └──────── BACKTRACK ◄──── BACKTRACK ◄── REPAIR LOOP
        """
        start_time = time.perf_counter()
        trace = PipelineDecisionTrace()

        # ──── Resolve LLM provider ─────────────────────────────────────
        if provider_type and provider_type != "mock":
            from interpretation.llm.live import LiveLLMProvider
            active_provider = LiveLLMProvider(provider=provider_type, model=llm_model)
            is_live = True
        else:
            active_provider = self.llm_provider
            is_live = False

        # ──── Main Retry Tree Loop ─────────────────────────────────────
        # Outer loop = backtracks (re-interpret when planning fails)
        last_validation_errors: Optional[list] = None
        best_proposal = None
        best_validation = None
        best_provider_name = "mock"

        for backtrack_idx in range(self.max_backtracks + 1):
            # ─── Stage 1: INTERPRET (with retry-on-error) ──────────────
            proposal = None
            provider_name = "mock"

            for attempt in range(1, self.max_interpret_retries + 1):
                t0 = time.perf_counter()
                try:
                    if hasattr(active_provider, 'interpret_with_retry'):
                        proposal, provider_name = active_provider.interpret_with_retry(
                            prompt=prompt,
                            domain=self.domain,
                            validation_errors=last_validation_errors,
                        )
                    else:
                        proposal = active_provider.interpret(prompt, self.domain)
                        provider_name = provider_type
                    t_ms = (time.perf_counter() - t0) * 1000.0

                    trace.stage_trace.append(StageAttemptRecord(
                        stage="INTERPRET",
                        attempt=attempt + (backtrack_idx * self.max_interpret_retries),
                        status=PipelineStageStatus.SUCCESS,
                        provider_used=provider_name,
                        duration_ms=t_ms,
                        recovery_action="retry_with_feedback" if last_validation_errors else None,
                    ))
                    trace.interpretation_attempts += 1
                    break

                except Exception as e:
                    t_ms = (time.perf_counter() - t0) * 1000.0
                    trace.stage_trace.append(StageAttemptRecord(
                        stage="INTERPRET",
                        attempt=attempt + (backtrack_idx * self.max_interpret_retries),
                        status=PipelineStageStatus.FAILED,
                        provider_used=provider_name,
                        duration_ms=t_ms,
                        error=str(e),
                        recovery_action="retry" if attempt < self.max_interpret_retries else "fallback_to_mock",
                    ))
                    trace.interpretation_attempts += 1
                    logger.warning(f"Interpretation attempt {attempt} failed: {e}")

                    if attempt >= self.max_interpret_retries:
                        # Last resort: use mock fallback
                        proposal = self.llm_provider.interpret(prompt, self.domain)
                        provider_name = "mock_fallback"
                        trace.stage_trace.append(StageAttemptRecord(
                            stage="INTERPRET",
                            attempt=attempt + 1,
                            status=PipelineStageStatus.SUCCESS,
                            provider_used="mock_fallback",
                            duration_ms=0.0,
                            recovery_action="mock_fallback",
                        ))

            if proposal is None:
                proposal = self.llm_provider.interpret(prompt, self.domain)
                provider_name = "mock_fallback"

            # Optional Vision perception integration
            if image is not None:
                scene_proposal = self.vision_detector.detect(image)
                for obj in scene_proposal.detected_objects:
                    if obj.name not in proposal.entities:
                        proposal.entities[obj.name] = obj.object_type

            # ─── Stage 2: VALIDATE (with retry-re-prompt) ─────────────
            t1 = time.perf_counter()
            val_res = self.validator.validate(proposal, self.domain)
            t_val_ms = (time.perf_counter() - t1) * 1000.0

            if not val_res.is_valid:
                trace.stage_trace.append(StageAttemptRecord(
                    stage="VALIDATE",
                    attempt=backtrack_idx + 1,
                    status=PipelineStageStatus.FAILED,
                    duration_ms=t_val_ms,
                    error="; ".join(val_res.errors),
                    recovery_action="retry_with_feedback" if backtrack_idx < self.max_backtracks else None,
                ))
                trace.validation_retries += 1

                # If we can retry, feed errors back to interpretation
                if backtrack_idx < self.max_backtracks:
                    last_validation_errors = val_res.errors
                    trace.backtracks += 1
                    trace.recovery_path.append(f"backtrack_validation_errors_{backtrack_idx + 1}")
                    logger.info(f"Validation failed, backtracking to re-interpret (attempt {backtrack_idx + 2})")
                    continue  # ← BACKTRACK to Stage 1

                # Exhausted backtracks — return validation failure
                elapsed = (time.perf_counter() - start_time) * 1000.0
                trace.total_attempts = sum(1 for s in trace.stage_trace if s.stage == "INTERPRET")
                trace.final_provider = provider_name
                dummy_verif = VerificationResultSchema(
                    is_valid=False,
                    failed_step_index=0,
                    explanation=f"Validation failed after {trace.backtracks} retries: {val_res.errors}",
                )
                return PipelineExecutionResult(
                    task_id=proposal.task_id,
                    raw_prompt=prompt,
                    has_image=(image is not None),
                    interpretation=proposal,
                    validation=val_res,
                    symbolic_problem_name="invalid_proposal",
                    planner_algorithm=algorithm,
                    candidate_plan=PlanSchema(actions=[], is_success=False),
                    initial_verification=dummy_verif,
                    final_verification=dummy_verif,
                    total_execution_time_ms=elapsed,
                    decision_trace=trace,
                )

            # Validation passed!
            trace.stage_trace.append(StageAttemptRecord(
                stage="VALIDATE",
                attempt=backtrack_idx + 1,
                status=PipelineStageStatus.SUCCESS,
                duration_ms=t_val_ms,
            ))
            best_proposal = proposal
            best_validation = val_res
            best_provider_name = provider_name

            # ─── Stage 3: PLAN (with cascade) ─────────────────────────
            problem = self.validator.convert_to_problem(proposal, self.domain)

            # Build planner cascade: start with requested algorithm, then add others
            cascade = [algorithm]
            for alt in PLANNER_CASCADE:
                if alt.upper() != algorithm.upper() and alt not in cascade:
                    cascade.append(alt)

            candidate = None
            used_algorithm = algorithm

            for planner_idx, algo_name in enumerate(cascade):
                t2 = time.perf_counter()
                try:
                    planner = get_planner_by_name(algo_name)
                    plan_result = planner.search(problem, self.domain)
                    t_plan_ms = (time.perf_counter() - t2) * 1000.0

                    if plan_result.is_success:
                        candidate = plan_result
                        used_algorithm = algo_name
                        trace.stage_trace.append(StageAttemptRecord(
                            stage="PLAN",
                            attempt=planner_idx + 1,
                            status=PipelineStageStatus.SUCCESS,
                            provider_used=algo_name,
                            duration_ms=t_plan_ms,
                            recovery_action="planner_cascade" if planner_idx > 0 else None,
                            details={"nodes_expanded": plan_result.nodes_expanded, "actions": len(plan_result.actions)},
                        ))
                        if planner_idx > 0:
                            trace.planner_cascades += 1
                            trace.recovery_path.append(f"planner_cascade_{algo_name}")
                        break

                    else:
                        trace.stage_trace.append(StageAttemptRecord(
                            stage="PLAN",
                            attempt=planner_idx + 1,
                            status=PipelineStageStatus.FAILED,
                            provider_used=algo_name,
                            duration_ms=t_plan_ms,
                            error=plan_result.failure_reason,
                            recovery_action="planner_cascade" if planner_idx < len(cascade) - 1 else "backtrack",
                        ))

                except Exception as e:
                    t_plan_ms = (time.perf_counter() - t2) * 1000.0
                    trace.stage_trace.append(StageAttemptRecord(
                        stage="PLAN",
                        attempt=planner_idx + 1,
                        status=PipelineStageStatus.FAILED,
                        provider_used=algo_name,
                        duration_ms=t_plan_ms,
                        error=str(e),
                    ))
                    logger.warning(f"Planner {algo_name} failed: {e}")

            if candidate is None:
                # All planners failed — backtrack to re-interpretation
                if backtrack_idx < self.max_backtracks:
                    last_validation_errors = [
                        "The planner could not find any valid plan for your formalization. "
                        "Please simplify the goals or check entity names."
                    ]
                    trace.backtracks += 1
                    trace.recovery_path.append(f"backtrack_planning_failed_{backtrack_idx + 1}")
                    logger.info(f"All planners failed, backtracking to re-interpret (attempt {backtrack_idx + 2})")
                    continue  # ← BACKTRACK to Stage 1

                # Exhausted — return planning failure
                elapsed = (time.perf_counter() - start_time) * 1000.0
                trace.total_attempts = sum(1 for s in trace.stage_trace if s.stage == "INTERPRET")
                trace.final_provider = provider_name
                trace.final_algorithm = used_algorithm
                dummy_verif = VerificationResultSchema(
                    is_valid=False,
                    failed_step_index=0,
                    explanation="All planners exhausted; no valid plan found after backtracks.",
                )
                return PipelineExecutionResult(
                    task_id=proposal.task_id,
                    raw_prompt=prompt,
                    has_image=(image is not None),
                    interpretation=proposal,
                    validation=val_res,
                    symbolic_problem_name=problem.name,
                    planner_algorithm=used_algorithm,
                    candidate_plan=PlanSchema(actions=[], is_success=False),
                    initial_verification=dummy_verif,
                    final_verification=dummy_verif,
                    total_execution_time_ms=elapsed,
                    decision_trace=trace,
                )

            # In demonstration mode: inject planning error for repair loop showcase
            if force_invalid_first_candidate and candidate.actions:
                mutated_actions = list(candidate.actions)
                if len(mutated_actions) >= 2:
                    mutated_actions[0], mutated_actions[1] = mutated_actions[1], mutated_actions[0]
                else:
                    mutated_actions = [GroundActionSchema(name="stack", arguments=("red_box", "blue_box"))]
                candidate = PlanSchema(
                    actions=mutated_actions,
                    algorithm="DemonstrationCandidate",
                    total_cost=candidate.total_cost,
                )

            # ─── Stage 4: VERIFY ──────────────────────────────────────
            t3 = time.perf_counter()
            v_res = self.verifier.verify(problem, self.domain, candidate)
            t_verif_ms = (time.perf_counter() - t3) * 1000.0

            cex = None
            attribution = None
            repairs = []
            replan_res = None
            final_plan = candidate
            final_verif = v_res

            if v_res.is_valid:
                trace.stage_trace.append(StageAttemptRecord(
                    stage="VERIFY",
                    attempt=1,
                    status=PipelineStageStatus.SUCCESS,
                    duration_ms=t_verif_ms,
                ))
            else:
                trace.stage_trace.append(StageAttemptRecord(
                    stage="VERIFY",
                    attempt=1,
                    status=PipelineStageStatus.FAILED,
                    duration_ms=t_verif_ms,
                    error=v_res.explanation,
                    recovery_action="repair_loop",
                ))

                # ─── Stage 5: REPAIR LOOP ─────────────────────────────
                cex = self.cex_generator.generate(v_res, problem)
                if cex:
                    attribution = self.attribution_engine.attribute(
                        counterexample=cex,
                        problem=problem,
                        candidate_plan=candidate,
                        natural_language_prompt=prompt,
                    )

                t4 = time.perf_counter()
                self.replanning_engine.planner = planner
                replan_res = self.replanning_engine.run_repair_loop(
                    problem=problem,
                    domain=self.domain,
                    initial_candidate=candidate,
                    natural_language_prompt=prompt,
                )
                t_repair_ms = (time.perf_counter() - t4) * 1000.0

                if replan_res.success:
                    final_plan = replan_res.repaired_plan
                    repairs = replan_res.repairs_applied
                    final_verif = replan_res.final_verification or v_res
                    trace.stage_trace.append(StageAttemptRecord(
                        stage="REPAIR",
                        attempt=1,
                        status=PipelineStageStatus.SUCCESS,
                        duration_ms=t_repair_ms,
                        details={"iterations": replan_res.iterations},
                    ))
                else:
                    trace.stage_trace.append(StageAttemptRecord(
                        stage="REPAIR",
                        attempt=1,
                        status=PipelineStageStatus.FAILED,
                        duration_ms=t_repair_ms,
                        error=replan_res.status,
                        recovery_action="backtrack" if backtrack_idx < self.max_backtracks else None,
                    ))

                    # Repair failed — backtrack to re-interpretation
                    if backtrack_idx < self.max_backtracks:
                        last_validation_errors = [
                            f"Plan repair failed ({replan_res.status}). "
                            "The formalization may be incorrect. "
                            "Please re-examine entity relationships and goal conditions."
                        ]
                        trace.backtracks += 1
                        trace.recovery_path.append(f"backtrack_repair_failed_{backtrack_idx + 1}")
                        logger.info(f"Repair failed, backtracking to re-interpret (attempt {backtrack_idx + 2})")
                        continue  # ← BACKTRACK to Stage 1

                    # Exhausted — return with partial results
                    final_plan = replan_res.repaired_plan or candidate
                    repairs = replan_res.repairs_applied
                    final_verif = replan_res.final_verification or v_res

            # ─── SUCCESS: Build final result ───────────────────────────
            elapsed = (time.perf_counter() - start_time) * 1000.0
            trace.total_attempts = sum(1 for s in trace.stage_trace if s.stage == "INTERPRET")
            trace.final_provider = best_provider_name
            trace.final_algorithm = used_algorithm

            return PipelineExecutionResult(
                task_id=proposal.task_id,
                raw_prompt=prompt,
                has_image=(image is not None),
                interpretation=proposal,
                validation=val_res,
                symbolic_problem_name=problem.name,
                planner_algorithm=used_algorithm,
                candidate_plan=candidate,
                initial_verification=v_res,
                counterexample=cex,
                fault_attribution=attribution,
                repairs_applied=repairs,
                replanning_result=replan_res,
                final_plan=final_plan,
                final_verification=final_verif,
                total_execution_time_ms=elapsed,
                decision_trace=trace,
            )

        # Should not reach here, but safety fallback
        elapsed = (time.perf_counter() - start_time) * 1000.0
        trace.total_attempts = sum(1 for s in trace.stage_trace if s.stage == "INTERPRET")
        dummy_verif = VerificationResultSchema(
            is_valid=False,
            failed_step_index=0,
            explanation="Pipeline exhausted all backtrack attempts.",
        )
        fallback_proposal = best_proposal or TaskProposalSchema(raw_prompt=prompt)
        fallback_validation = best_validation or ProposalValidationResult(
            status="SCHEMA_ERROR", is_valid=False, errors=["All attempts exhausted"]
        )
        return PipelineExecutionResult(
            task_id=fallback_proposal.task_id,
            raw_prompt=prompt,
            has_image=(image is not None),
            interpretation=fallback_proposal,
            validation=fallback_validation,
            symbolic_problem_name="exhausted",
            planner_algorithm=algorithm,
            candidate_plan=PlanSchema(actions=[], is_success=False),
            initial_verification=dummy_verif,
            final_verification=dummy_verif,
            total_execution_time_ms=elapsed,
            decision_trace=trace,
        )
