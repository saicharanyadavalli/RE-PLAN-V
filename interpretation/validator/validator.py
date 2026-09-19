"""Schema and consistency validator for untrusted neural proposals."""

from __future__ import annotations

from typing import List, Optional, Set, Tuple
from core.actions.domain import Domain
from core.contracts import (
    FactSchema,
    ProposalValidationResult,
    TaskProposalSchema,
    ValidationStatus,
)
from core.world.constraints import NegativeFactInvariant, ProhibitedEntityActionConstraint
from core.world.predicates import Fact
from core.world.problem import SymbolicProblem
from core.world.state import SymbolicState
from core.world.types import ObjectRegistry


class ConsistencyValidator:
    """Validates untrusted neural proposals before allowing symbolic processing."""

    def validate(
        self,
        proposal: TaskProposalSchema,
        domain: Domain,
    ) -> ProposalValidationResult:
        errors: List[str] = []
        warnings: List[str] = []

        # 1. Validate Entities
        if not proposal.entities:
            errors.append("Proposal must define at least one entity.")

        registry = ObjectRegistry(domain.type_hierarchy)
        for name, type_name in proposal.entities.items():
            registry.register_object(name, type_name)

        # 2. Check Entity References in Facts
        all_facts = proposal.initial_facts + proposal.goal_facts + proposal.negative_constraints + proposal.invariants
        for f in all_facts:
            for arg in f.arguments:
                if arg not in proposal.entities:
                    errors.append(
                        f"Unknown entity reference '{arg}' in condition '{f.to_string()}'. Must be in entities dict."
                    )

        # 3. Validate Predicates and Arities against Domain
        for f in all_facts:
            pred_name = f.predicate.lower()
            if pred_name not in domain.predicates:
                errors.append(
                    f"Unsupported predicate '{f.predicate}' in condition '{f.to_string()}'. Not defined in domain '{domain.name}'."
                )
            else:
                pred_def = domain.predicates[pred_name]
                if len(f.arguments) != pred_def.arity:
                    errors.append(
                        f"Arity mismatch for '{pred_name}' in '{f.to_string()}': expected {pred_def.arity} arguments, got {len(f.arguments)}."
                    )

        # 4. Check for Direct Logical Contradictions in Initial Facts
        seen_facts: Set[Tuple[str, Tuple[str, ...]]] = set()
        seen_neg_facts: Set[Tuple[str, Tuple[str, ...]]] = set()

        for f in proposal.initial_facts:
            key = (f.predicate.lower(), tuple(f.arguments))
            if f.is_negated:
                if key in seen_facts:
                    errors.append(f"Contradiction in initial state: fact '{f.predicate}' declared both True and False.")
                seen_neg_facts.add(key)
            else:
                if key in seen_neg_facts:
                    errors.append(f"Contradiction in initial state: fact '{f.predicate}' declared both True and False.")
                seen_facts.add(key)

        # Check domain-specific mutex contradictions (e.g. holding(x) and handempty())
        holding_facts = [f for f in proposal.initial_facts if f.predicate.lower() == "holding" and not f.is_negated]
        handempty_facts = [f for f in proposal.initial_facts if f.predicate.lower() == "handempty" and not f.is_negated]
        if holding_facts and handempty_facts:
            errors.append("Contradictory state: robot cannot be holding an object while handempty() holds.")

        if errors:
            status = ValidationStatus.CONTRADICTION if "Contradiction" in errors[0] else ValidationStatus.SCHEMA_ERROR
            if any("Unknown entity" in e for e in errors):
                status = ValidationStatus.UNKNOWN_ENTITY
            elif any("Arity mismatch" in e for e in errors):
                status = ValidationStatus.ARITY_MISMATCH
            elif any("Unsupported predicate" in e for e in errors):
                status = ValidationStatus.UNSUPPORTED_OPERATOR

            return ProposalValidationResult(
                status=status,
                is_valid=False,
                errors=errors,
                warnings=warnings,
                validated_proposal=None,
            )

        return ProposalValidationResult(
            status=ValidationStatus.VALID,
            is_valid=True,
            errors=[],
            warnings=warnings,
            validated_proposal=proposal,
        )

    def convert_to_problem(
        self,
        proposal: TaskProposalSchema,
        domain: Domain,
        problem_name: str = "neural_task",
    ) -> SymbolicProblem:
        """Converts a validated proposal into an authoritative SymbolicProblem instance."""
        reg = ObjectRegistry(domain.type_hierarchy)
        for name, type_name in proposal.entities.items():
            reg.register_object(name, type_name)

        init_facts = [Fact.from_schema(f) for f in proposal.initial_facts]
        init_state = SymbolicState(facts=init_facts, objects=reg.get_all_objects())

        goal_facts = [Fact.from_schema(g) for g in proposal.goal_facts]

        # Convert negative constraints to Invariants or HardConstraints
        invariants = []
        hard_constraints = []

        for neg in proposal.negative_constraints:
            fact_cond = Fact.from_schema(neg)
            invariants.append(NegativeFactInvariant(fact_cond.positive_version()))
            if fact_cond.arguments:
                hard_constraints.append(
                    ProhibitedEntityActionConstraint(
                        protected_entity=fact_cond.arguments[0],
                        prohibited_actions=[],
                        description=f"Protect {fact_cond.arguments[0]} as requested in task.",
                    )
                )

        return SymbolicProblem(
            name=problem_name,
            domain_name=domain.name,
            registry=reg,
            initial_state=init_state,
            goal_conditions=goal_facts,
            invariants=invariants,
            hard_constraints=hard_constraints,
            description=proposal.raw_prompt,
        )
