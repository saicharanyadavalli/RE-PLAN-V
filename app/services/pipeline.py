"""End-to-end pipeline orchestrator for RE-PLAN-V."""

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
    PlanSchema,
    ProposalValidationResult,
    RepairConstraintSchema,
    ReplanningResultSchema,
    TaskProposalSchema,
    VerificationResultSchema,
    WorldDeltaSchema,
)
from core.counterexamples.generator import CounterexampleGenerator
from core.repair.generator import RepairGenerator
from core.replanning.loop import ReplanningEngine
from core.search.algorithms import BasePlanner, get_planner_by_name
from core.verification.verifier import PlanVerifier
from core.world.problem import SymbolicProblem
from interpretation.llm.base import BaseLLMProvider
from interpretation.llm.mock import MockLLMProvider
from interpretation.validator.validator import ConsistencyValidator
from interpretation.vision.detector import DeterministicSceneDetector


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


class PipelineOrchestrator:
    """Coordinates interpretation, validation, planning, verification, attribution, and repair."""

    def __init__(
        self,
        llm_provider: Optional[BaseLLMProvider] = None,
        validator: Optional[ConsistencyValidator] = None,
        verifier: Optional[PlanVerifier] = None,
        replanning_engine: Optional[ReplanningEngine] = None,
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

    def run(
        self,
        prompt: str,
        image: Optional[Image.Image] = None,
        algorithm: str = "A*",
        force_invalid_first_candidate: bool = False,
        provider_type: str = "mock",
        llm_model: Optional[str] = None,
    ) -> PipelineExecutionResult:
        """Executes the full pipeline from natural language prompt to verified final plan."""
        start_time = time.perf_counter()

        # Step 1: Neural Interpretation
        if provider_type and provider_type != "mock":
            from interpretation.llm.live import LiveLLMProvider
            active_provider: BaseLLMProvider = LiveLLMProvider(provider=provider_type, model=llm_model)
        else:
            active_provider = self.llm_provider

        proposal = active_provider.interpret(prompt, self.domain)


        # Optional Vision perception integration if image is provided
        if image is not None:
            scene_proposal = self.vision_detector.detect(image)
            # Enrich or synchronize entities and facts
            for obj in scene_proposal.detected_objects:
                if obj.name not in proposal.entities:
                    proposal.entities[obj.name] = obj.object_type

        # Step 2: Schema and Consistency Validation
        val_res = self.validator.validate(proposal, self.domain)
        if not val_res.is_valid:
            elapsed = (time.perf_counter() - start_time) * 1000.0
            dummy_verif = VerificationResultSchema(
                is_valid=False,
                failed_step_index=0,
                explanation=f"Validation failed: {val_res.errors}",
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
            )

        # Step 3: Authoritative Symbolic Problem
        problem = self.validator.convert_to_problem(proposal, self.domain)

        # Step 4: Search Planning
        planner = get_planner_by_name(algorithm)
        candidate = planner.search(problem, self.domain)

        # In demonstration mode: if user wants to showcase the repair loop on an initial plan
        if force_invalid_first_candidate and candidate.actions:
            # Inject a planning error (swap order of actions) to trigger the verification-repair cycle
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

        # Step 5: Formal Verification of Candidate Plan
        v_res = self.verifier.verify(problem, self.domain, candidate)

        cex = None
        attribution = None
        repairs = []
        replan_res = None
        final_plan = candidate
        final_verif = v_res

        # Step 6: If Invalid, execute Repair and Replanning Loop
        if not v_res.is_valid:
            cex = self.cex_generator.generate(v_res, problem)
            if cex:
                attribution = self.attribution_engine.attribute(
                    counterexample=cex,
                    problem=problem,
                    candidate_plan=candidate,
                    natural_language_prompt=prompt,
                )

            # Run complete repair loop
            self.replanning_engine.planner = planner
            replan_res = self.replanning_engine.run_repair_loop(
                problem=problem,
                domain=self.domain,
                initial_candidate=candidate,
                natural_language_prompt=prompt,
            )

            final_plan = replan_res.repaired_plan
            repairs = replan_res.repairs_applied
            final_verif = replan_res.final_verification or v_res

        elapsed = (time.perf_counter() - start_time) * 1000.0

        return PipelineExecutionResult(
            task_id=proposal.task_id,
            raw_prompt=prompt,
            has_image=(image is not None),
            interpretation=proposal,
            validation=val_res,
            symbolic_problem_name=problem.name,
            planner_algorithm=algorithm,
            candidate_plan=candidate,
            initial_verification=v_res,
            counterexample=cex,
            fault_attribution=attribution,
            repairs_applied=repairs,
            replanning_result=replan_res,
            final_plan=final_plan,
            final_verification=final_verif,
            total_execution_time_ms=elapsed,
        )
