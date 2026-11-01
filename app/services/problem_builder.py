"""Single authoritative validated task formalization and problem construction service.

Shared across:
- PipelineOrchestrator.run
- REST /api/graph/enumerate
- WebSocket /ws/pipeline
- Standalone /api/llm/formalize

Guarantees 100% semantic parity for entities, predicates, invariants,
typed action constraints, and initial state validation before planning or enumeration.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from core.actions.domain import Domain
from core.contracts import (
    ProposalValidationResult,
    TaskProposalSchema,
    ValidationStatus,
)
from core.domains import DomainRegistry, registry as default_registry
from core.world.problem import SymbolicProblem
from interpretation.llm.base import BaseLLMProvider
from interpretation.llm.mock import MockLLMProvider
from interpretation.router import DomainRouter, DomainRoutingResult, RoutingOutcome
from interpretation.validator.validator import ConsistencyValidator


@dataclass
class ProblemBuildResult:
    """Typed result of problem formalization and validation."""
    is_success: bool
    domain: Optional[Domain] = None
    proposal: Optional[TaskProposalSchema] = None
    problem: Optional[SymbolicProblem] = None
    outcome: RoutingOutcome = RoutingOutcome.SUPPORTED
    status: str = "SUCCESS"  # "SUCCESS", "UNSUPPORTED", "NEEDS_CLARIFICATION", "INVALID", "INVARIANT_VIOLATION"
    error_message: Optional[str] = None
    clarification_question: Optional[str] = None
    validation_result: Optional[ProposalValidationResult] = None
    routing_result: Optional[DomainRoutingResult] = None


class ValidatedProblemBuilder:
    """Authoritative builder constructing validated SymbolicProblem instances."""

    def __init__(
        self,
        registry: Optional[DomainRegistry] = None,
        validator: Optional[ConsistencyValidator] = None,
        llm_provider: Optional[BaseLLMProvider] = None,
    ) -> None:
        self.registry = registry or default_registry
        self.router = DomainRouter(registry=self.registry)
        self.validator = validator or ConsistencyValidator()
        self.llm_provider = llm_provider or MockLLMProvider()

    def build_from_proposal(
        self,
        proposal: TaskProposalSchema,
        domain: Domain,
        *,
        problem_name: str = "validated_task",
        routing_result: Optional[DomainRoutingResult] = None,
    ) -> ProblemBuildResult:
        """Constructs an authoritative, fully validated SymbolicProblem from an existing proposal.

        Accepts an already interpreted proposal and an already resolved registered domain.
        Does NOT call the LLM or perform domain routing.
        """
        # Merge routing_result.typed_constraints and routing_result.negative_constraints only
        # when the proposal does not already contain the relevant values, preserving explicit
        # proposal constraints and avoiding duplicates.
        if routing_result is not None:
            if routing_result.typed_constraints:
                if proposal.typed_constraints is None:
                    proposal.typed_constraints = []
                for tc in routing_result.typed_constraints:
                    if tc not in proposal.typed_constraints:
                        proposal.typed_constraints.append(tc)

            if routing_result.negative_constraints:
                if proposal.negative_constraints is None:
                    proposal.negative_constraints = []
                for nc in routing_result.negative_constraints:
                    if nc not in proposal.negative_constraints:
                        proposal.negative_constraints.append(nc)

        # Validate proposal using self.validator.validate
        val_res = self.validator.validate(proposal, domain)
        if not val_res.is_valid:
            return ProblemBuildResult(
                is_success=False,
                domain=domain,
                proposal=proposal,
                outcome=RoutingOutcome.INVALID_PROPOSAL,
                status="INVALID",
                error_message="; ".join(val_res.errors),
                validation_result=val_res,
                routing_result=routing_result,
            )

        validated_proposal = val_res.validated_proposal or proposal

        # Convert to SymbolicProblem
        problem = self.validator.convert_to_problem(
            validated_proposal,
            domain,
            problem_name=problem_name,
        )

        # Check initial state against BOTH domain invariants and problem invariants
        dom_ok, dom_err = domain.check_invariants(problem.initial_state)
        if not dom_ok:
            return ProblemBuildResult(
                is_success=False,
                domain=domain,
                proposal=validated_proposal,
                problem=problem,
                status="INVARIANT_VIOLATION",
                error_message=f"Initial state violates invariants: {dom_err}",
                validation_result=ProposalValidationResult(
                    status=ValidationStatus.CONTRADICTION,
                    is_valid=False,
                    errors=[f"Initial state invariant violation: {dom_err}"],
                    validated_proposal=None,
                ),
                routing_result=routing_result,
            )

        prob_ok, prob_err = problem.check_invariants(problem.initial_state)
        if not prob_ok:
            return ProblemBuildResult(
                is_success=False,
                domain=domain,
                proposal=validated_proposal,
                problem=problem,
                status="INVARIANT_VIOLATION",
                error_message=f"Initial state violates invariants: {prob_err}",
                validation_result=ProposalValidationResult(
                    status=ValidationStatus.CONTRADICTION,
                    is_valid=False,
                    errors=[f"Initial state invariant violation: {prob_err}"],
                    validated_proposal=None,
                ),
                routing_result=routing_result,
            )

        return ProblemBuildResult(
            is_success=True,
            domain=domain,
            proposal=validated_proposal,
            problem=problem,
            status="SUCCESS",
            validation_result=val_res,
            routing_result=routing_result,
        )

    def build_problem(
        self,
        prompt: str,
        domain_id: Optional[str] = None,
        provider_type: str = "mock",
        llm_model: Optional[str] = None,
        problem_name: str = "validated_task",
    ) -> ProblemBuildResult:
        """Constructs an authoritative, fully validated SymbolicProblem from text.
        
        Enforces domain resolution, schema bounds, invariants, typed prohibitions,
        and initial state validity before handing off to search or enumeration.
        """
        # Step 1: Explicit or automatic domain routing
        routing = self.router.route(
            prompt,
            explicit_domain_id=domain_id if (domain_id and domain_id != "auto") else None,
        )

        if routing.outcome == RoutingOutcome.NEEDS_CLARIFICATION:
            return ProblemBuildResult(
                is_success=False,
                outcome=RoutingOutcome.NEEDS_CLARIFICATION,
                status="NEEDS_CLARIFICATION",
                error_message=routing.explanation or "Prompt is ambiguous and requires clarification.",
                clarification_question=routing.clarification_question,
                routing_result=routing,
            )

        if routing.outcome != RoutingOutcome.SUPPORTED or not routing.selected_domain_id:
            return ProblemBuildResult(
                is_success=False,
                outcome=RoutingOutcome.UNSUPPORTED,
                status="UNSUPPORTED",
                error_message=routing.explanation or f"Task could not be routed to a supported domain.",
                routing_result=routing,
            )

        target_domain_id = routing.selected_domain_id
        domain = self.registry.get(target_domain_id)
        if not domain:
            return ProblemBuildResult(
                is_success=False,
                outcome=RoutingOutcome.UNSUPPORTED,
                status="UNSUPPORTED",
                error_message=f"Requested domain '{target_domain_id}' is not registered.",
                routing_result=routing,
            )

        # Step 2: Proposal generation
        is_live = provider_type and provider_type != "mock"
        if is_live:
            from interpretation.llm.live import LiveLLMProvider
            active_provider: BaseLLMProvider = LiveLLMProvider(provider=provider_type, model=llm_model)
        else:
            active_provider = self.llm_provider

        try:
            proposal = active_provider.interpret(prompt, domain)
        except Exception as e:
            return ProblemBuildResult(
                is_success=False,
                domain=domain,
                outcome=RoutingOutcome.INVALID_PROPOSAL,
                status="INVALID",
                error_message=f"Interpretation provider error: {str(e)}",
                routing_result=routing,
            )

        # If proposal is empty, fail closed
        if not proposal.entities or not proposal.goal_facts:
            return ProblemBuildResult(
                is_success=False,
                domain=domain,
                proposal=proposal,
                outcome=RoutingOutcome.UNSUPPORTED,
                status="UNSUPPORTED",
                error_message="Prompt formalization yielded zero entities or goals; failing closed.",
                routing_result=routing,
            )

        # Delegate validation, constraint merging, and SymbolicProblem construction to build_from_proposal
        return self.build_from_proposal(
            proposal=proposal,
            domain=domain,
            problem_name=problem_name,
            routing_result=routing,
        )
