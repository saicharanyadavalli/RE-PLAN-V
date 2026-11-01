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
    ValidationStatus,
    VerificationResultSchema,
    ViolationType,
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
from app.services.problem_builder import ValidatedProblemBuilder

logger = get_logger("pipeline")

# Planner cascade order: try A* first (optimal), then BFS (complete), then Best-First (fast)
PLANNER_CASCADE = ["A*", "BFS", "BEST_FIRST"]


class PipelineExecutionResult(BaseModel):
    """Complete, end-to-end trace of a task through the RE-PLAN-V pipeline."""
    task_id: str
    raw_prompt: str
    status: str = "COMPLETED"
    domain_id: Optional[str] = None
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

    @property
    def is_verified(self) -> bool:
        return bool(self.final_verification and self.final_verification.is_valid)


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
        domain: Optional[Domain] = None,
        domain_id: Optional[str] = None,
        llm_provider: Optional[BaseLLMProvider] = None,
        validator: Optional[ConsistencyValidator] = None,
        verifier: Optional[PlanVerifier] = None,
        replanning_engine: Optional[ReplanningEngine] = None,
        problem_builder: Optional[ValidatedProblemBuilder] = None,
        max_interpret_retries: int = 3,
        max_backtracks: int = 2,
    ) -> None:
        from core.domains import registry
        if domain is not None:
            self.domain = domain
        elif domain_id is not None:
            found = registry.get(domain_id)
            if not found:
                raise ValueError(f"Unregistered domain '{domain_id}'. Available domains: {[d.domain_id for d in registry.list_domains()]}")
            self.domain = found
        else:
            self.domain = create_blocks_world_domain()
        self.llm_provider = llm_provider or MockLLMProvider()
        self.validator = validator or ConsistencyValidator()
        self.verifier = verifier or PlanVerifier()
        self.replanning_engine = replanning_engine or ReplanningEngine(verifier=self.verifier)
        from app.services.problem_builder import ValidatedProblemBuilder
        self.problem_builder = problem_builder or ValidatedProblemBuilder(
            validator=self.validator,
            llm_provider=self.llm_provider,
        )
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
        provider_type: Optional[str] = None,
        llm_model: Optional[str] = None,
        domain_id: Optional[str] = None,
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

        # ──── Resolve Active Domain ─────────────────────────────────────
        active_domain = self.domain
        routed_domain_id = getattr(self.domain, "domain_id", "blocks_world")
        if domain_id:
            from core.domains import registry
            if domain_id == "auto":
                from interpretation.router import DomainRouter, RoutingOutcome
                router = DomainRouter(registry=registry)
                routing = router.route(prompt)

                if routing.outcome != RoutingOutcome.SUPPORTED or not routing.selected_domain_id:
                    elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                    status_name = routing.outcome.value if hasattr(routing.outcome, "value") else str(routing.outcome)
                    explanation = routing.explanation or f"Task cannot proceed: routing outcome is {status_name}."
                    return PipelineExecutionResult(
                        task_id=f"rejected_{status_name.lower()}",
                        raw_prompt=prompt,
                        status=status_name,
                        domain_id=None,
                        interpretation=TaskProposalSchema(
                            task_id=f"rejected_{status_name.lower()}",
                            raw_prompt=prompt,
                            entities={},
                            initial_facts=[],
                            goal_facts=[],
                            confidence=0.0,
                        ),
                        validation=ProposalValidationResult(
                            status=ValidationStatus.SCHEMA_ERROR,
                            is_valid=False,
                            errors=[explanation],
                            warnings=[],
                            validated_proposal=None,
                        ),
                        symbolic_problem_name="none",
                        planner_algorithm=algorithm,
                        candidate_plan=PlanSchema(actions=[], is_success=False, failure_reason=explanation),
                        initial_verification=VerificationResultSchema(
                            is_valid=False,
                            violation_type=ViolationType.NONE,
                            explanation=explanation,
                        ),
                        final_plan=None,
                        final_verification=VerificationResultSchema(
                            is_valid=False,
                            violation_type=ViolationType.NONE,
                            explanation=explanation,
                        ),
                        total_execution_time_ms=elapsed_ms,
                        decision_trace=trace,
                    )

                matched = registry.get(routing.selected_domain_id)
                if not matched:
                    elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                    err = f"Routed domain '{routing.selected_domain_id}' not found in registry."
                    return PipelineExecutionResult(
                        task_id="rejected_unregistered_domain",
                        raw_prompt=prompt,
                        status="UNREGISTERED_DOMAIN",
                        domain_id=routing.selected_domain_id,
                        interpretation=TaskProposalSchema(
                            task_id="rejected_unregistered_domain",
                            raw_prompt=prompt,
                            entities={},
                            initial_facts=[],
                            goal_facts=[],
                            confidence=0.0,
                        ),
                        validation=ProposalValidationResult(
                            status=ValidationStatus.SCHEMA_ERROR,
                            is_valid=False,
                            errors=[err],
                            warnings=[],
                            validated_proposal=None,
                        ),
                        symbolic_problem_name="none",
                        planner_algorithm=algorithm,
                        candidate_plan=PlanSchema(actions=[], is_success=False, failure_reason=err),
                        initial_verification=VerificationResultSchema(
                            is_valid=False,
                            violation_type=ViolationType.NONE,
                            explanation=err,
                        ),
                        final_plan=None,
                        final_verification=VerificationResultSchema(
                            is_valid=False,
                            violation_type=ViolationType.NONE,
                            explanation=err,
                        ),
                        total_execution_time_ms=elapsed_ms,
                        decision_trace=trace,
                    )
                active_domain = matched
                routed_domain_id = active_domain.domain_id
            else:
                matched = registry.get(domain_id)
                if not matched:
                    elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                    err = f"Explicit domain '{domain_id}' is not registered."
                    return PipelineExecutionResult(
                        task_id="rejected_unknown_domain",
                        raw_prompt=prompt,
                        status="INVALID_DOMAIN",
                        domain_id=domain_id,
                        interpretation=TaskProposalSchema(
                            task_id="rejected_unknown_domain",
                            raw_prompt=prompt,
                            entities={},
                            initial_facts=[],
                            goal_facts=[],
                            confidence=0.0,
                        ),
                        validation=ProposalValidationResult(
                            status=ValidationStatus.SCHEMA_ERROR,
                            is_valid=False,
                            errors=[err],
                            warnings=[],
                            validated_proposal=None,
                        ),
                        symbolic_problem_name="none",
                        planner_algorithm=algorithm,
                        candidate_plan=PlanSchema(actions=[], is_success=False, failure_reason=err),
                        initial_verification=VerificationResultSchema(
                            is_valid=False,
                            violation_type=ViolationType.NONE,
                            explanation=err,
                        ),
                        final_plan=None,
                        final_verification=VerificationResultSchema(
                            is_valid=False,
                            violation_type=ViolationType.NONE,
                            explanation=err,
                        ),
                        total_execution_time_ms=elapsed_ms,
                        decision_trace=trace,
                    )
                active_domain = matched
                routed_domain_id = active_domain.domain_id

        # ──── Resolve LLM provider ─────────────────────────────────────
        import os
        effective_provider = provider_type
        if effective_provider is None:
            if not isinstance(self.llm_provider, MockLLMProvider):
                effective_provider = "custom"
            else:
                env_provider = os.environ.get("LLM_PROVIDER", "").strip().lower()
                if env_provider and env_provider != "mock":
                    effective_provider = env_provider
                else:
                    effective_provider = "mock"

        if effective_provider not in ("mock", "custom", "", None):
            from interpretation.llm.live import LiveLLMProvider
            active_provider = LiveLLMProvider(provider=effective_provider, model=llm_model)
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
                            domain=active_domain,
                            validation_errors=last_validation_errors,
                        )
                    else:
                        proposal = active_provider.interpret(prompt, active_domain)
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
                        proposal = self.llm_provider.interpret(prompt, active_domain)
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
                proposal = self.llm_provider.interpret(prompt, active_domain)
                provider_name = "mock_fallback"

            # Merge routing-derived typed and negative constraints if interpreter did not populate them
            if 'routing' in locals() and routing:
                if getattr(routing, "typed_constraints", None) and not getattr(proposal, "typed_constraints", []):
                    proposal.typed_constraints = list(routing.typed_constraints)
                if getattr(routing, "negative_constraints", None) and not getattr(proposal, "negative_constraints", []):
                    proposal.negative_constraints = list(routing.negative_constraints)

            # Optional Vision perception integration
            if image is not None:
                scene_proposal = self.vision_detector.detect(image)
                for obj in scene_proposal.detected_objects:
                    if obj.name not in proposal.entities:
                        proposal.entities[obj.name] = obj.object_type

            # ─── Stage 2: VALIDATE (via Authoritative Problem Builder) ─
            t1 = time.perf_counter()
            build_res = self.problem_builder.build_from_proposal(
                proposal,
                active_domain,
                routing_result=routing if 'routing' in locals() else None,
            )
            t_val_ms = (time.perf_counter() - t1) * 1000.0

            if not build_res.is_success:
                if build_res.status == "INVARIANT_VIOLATION":
                    elapsed = (time.perf_counter() - start_time) * 1000.0
                    inv_err = build_res.error_message or "Initial state violates invariants"
                    verif_err = VerificationResultSchema(
                        is_valid=False,
                        failed_step_index=0,
                        explanation=f"Initial state violates invariants: {inv_err}" if not inv_err.startswith("Initial state violates") else inv_err,
                    )
                    inv_validation = build_res.validation_result or ProposalValidationResult(
                        status=ValidationStatus.CONTRADICTION,
                        is_valid=False,
                        errors=[f"Initial state invariant violation: {inv_err}"],
                        validated_proposal=None,
                    )
                    return PipelineExecutionResult(
                        task_id=proposal.task_id,
                        raw_prompt=prompt,
                        status="INVARIANT_VIOLATION",
                        domain_id=routed_domain_id,
                        has_image=(image is not None),
                        interpretation=build_res.proposal or proposal,
                        validation=inv_validation,
                        symbolic_problem_name="initial_state_invariant_violation",
                        planner_algorithm=algorithm,
                        candidate_plan=PlanSchema(actions=[], is_success=False, failure_reason=inv_err),
                        initial_verification=verif_err,
                        final_verification=verif_err,
                        total_execution_time_ms=elapsed,
                        decision_trace=trace,
                    )

                # Invalid proposal handling (status == "INVALID" or other validation errors)
                val_errors = (
                    build_res.validation_result.errors
                    if build_res.validation_result and build_res.validation_result.errors
                    else ([build_res.error_message] if build_res.error_message else ["Proposal validation failed"])
                )
                val_res = build_res.validation_result or ProposalValidationResult(
                    status=ValidationStatus.SCHEMA_ERROR,
                    is_valid=False,
                    errors=val_errors,
                    warnings=[],
                    validated_proposal=None,
                )
                error_msg = build_res.error_message or "; ".join(val_errors)

                trace.stage_trace.append(StageAttemptRecord(
                    stage="VALIDATE",
                    attempt=backtrack_idx + 1,
                    status=PipelineStageStatus.FAILED,
                    duration_ms=t_val_ms,
                    error=error_msg,
                    recovery_action="retry_with_feedback" if backtrack_idx < self.max_backtracks else None,
                ))
                trace.validation_retries += 1

                # If we can retry, feed errors back to interpretation
                if backtrack_idx < self.max_backtracks:
                    last_validation_errors = val_errors
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
                    explanation=f"Validation failed after {trace.backtracks} retries: {val_errors}",
                )
                return PipelineExecutionResult(
                    task_id=proposal.task_id,
                    raw_prompt=prompt,
                    status="INVALID_PROPOSAL",
                    domain_id=routed_domain_id,
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
            proposal = build_res.proposal or proposal
            problem = build_res.problem
            val_res = build_res.validation_result or ProposalValidationResult(
                status=ValidationStatus.VALID,
                is_valid=True,
                errors=[],
                warnings=[],
                validated_proposal=proposal,
            )
            best_proposal = proposal
            best_validation = val_res
            best_provider_name = provider_name

            # ─── Stage 3: PLAN (with cascade) ─────────────────────────

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
                    plan_result = planner.search(problem, active_domain)
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
                    status="INVALID_PROPOSAL",
                    domain_id=routed_domain_id,
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
            v_res = self.verifier.verify(problem, active_domain, candidate)
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
                    domain=active_domain,
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
                status="COMPLETED" if (final_verif and final_verif.is_valid) else "FAILED",
                domain_id=routed_domain_id,
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
            status="FAILED",
            domain_id=routed_domain_id,
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
