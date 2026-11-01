"""Schema and consistency validator for untrusted neural proposals."""

from __future__ import annotations

from typing import List, Optional, Set, Tuple
from core.actions.domain import Domain
from core.contracts import (
    FactSchema,
    ProposalValidationResult,
    TaskConstraintType,
    TaskProposalSchema,
    ValidationStatus,
)
from core.world.constraints import (
    ForbidActionBindingConstraint,
    ForbidActionConstraint,
    ForbidActionExactBindingConstraint,
    ForbidTransitionConstraint,
    HardConstraint,
    Invariant,
    NegativeFactInvariant,
    ProhibitedEntityActionConstraint,
)
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

        # 3. Validate Predicates, Arities, and Argument Types against Domain
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
                else:
                    for idx, (arg, exp_type) in enumerate(zip(f.arguments, pred_def.arg_types)):
                        actual_type = proposal.entities.get(arg)
                        if actual_type and not domain.type_hierarchy.is_subtype(actual_type, exp_type):
                            errors.append(
                                f"Type mismatch for predicate '{pred_name}' argument {idx} ('{arg}'): entity type '{actual_type}' is not a subtype of expected '{exp_type}'."
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

        # Check domain-specific mutex contradictions across all supported domains
        # 1. Blocks World mutexes
        holding_facts = [f for f in proposal.initial_facts if f.predicate.lower() == "holding" and not f.is_negated]
        handempty_facts = [f for f in proposal.initial_facts if f.predicate.lower() == "handempty" and not f.is_negated]
        if holding_facts and handempty_facts:
            errors.append("Contradictory state: robot cannot be holding an object while handempty() holds.")

        for h in holding_facts:
            if h.arguments:
                held_obj = h.arguments[0]
                if any(f.predicate.lower() == "on_table" and f.arguments and f.arguments[0] == held_obj and not f.is_negated for f in proposal.initial_facts):
                    errors.append(f"Mutex violation: object '{held_obj}' cannot be simultaneously holding and on_table.")

        # 2. Grid World mutexes
        carrying_facts = [f for f in proposal.initial_facts if f.predicate.lower() == "carrying" and not f.is_negated]
        empty_hand_facts = [f for f in proposal.initial_facts if f.predicate.lower() == "empty_hand" and not f.is_negated]
        if carrying_facts and empty_hand_facts:
            errors.append("Contradictory state: agent cannot be carrying an item while empty_hand() holds.")

        # 3. Household Robotics mutexes
        hh_holding = [f for f in proposal.initial_facts if f.predicate.lower() == "holding" and len(f.arguments) >= 2 and not f.is_negated]
        gripper_empty_facts = [f for f in proposal.initial_facts if f.predicate.lower() == "gripper_empty" and not f.is_negated]
        if hh_holding and gripper_empty_facts:
            errors.append("Contradictory state: robot cannot be holding an item while gripper_empty() holds.")

        open_containers = {f.arguments[0] for f in proposal.initial_facts if f.predicate.lower() == "container_open" and f.arguments and not f.is_negated}
        closed_containers = {f.arguments[0] for f in proposal.initial_facts if f.predicate.lower() == "container_closed" and f.arguments and not f.is_negated}
        both_c = open_containers.intersection(closed_containers)
        if both_c:
            errors.append(f"Contradictory state: container '{list(both_c)[0]}' cannot be simultaneously open and closed.")

        # 4. Warehouse Operations mutexes
        loaded_carriers = {f.arguments[0] for f in proposal.initial_facts if f.predicate.lower() == "carrier_loaded_with" and f.arguments and not f.is_negated}
        empty_carriers = {f.arguments[0] for f in proposal.initial_facts if f.predicate.lower() == "carrier_empty" and f.arguments and not f.is_negated}
        both_car = loaded_carriers.intersection(empty_carriers)
        if both_car:
            errors.append(f"Contradictory state: carrier '{list(both_car)[0]}' cannot be simultaneously loaded and empty.")

        occupied_bays = {f.arguments[0] for f in proposal.initial_facts if f.predicate.lower() == "bay_occupied" and f.arguments and not f.is_negated}
        avail_bays = {f.arguments[0] for f in proposal.initial_facts if f.predicate.lower() == "bay_available" and f.arguments and not f.is_negated}
        both_bays = occupied_bays.intersection(avail_bays)
        if both_bays:
            errors.append(f"Contradictory state: bay '{list(both_bays)[0]}' cannot be simultaneously occupied and available.")

        # 5. Scheduling mutexes
        avail_res = {(f.arguments[0], f.arguments[1]) for f in proposal.initial_facts if f.predicate.lower() == "resource_available" and len(f.arguments) >= 2 and not f.is_negated}
        busy_res = {(f.arguments[0], f.arguments[1]) for f in proposal.initial_facts if f.predicate.lower() == "resource_busy" and len(f.arguments) >= 2 and not f.is_negated}
        both_res = avail_res.intersection(busy_res)
        if both_res:
            res_item = list(both_res)[0]
            errors.append(f"Contradictory state: resource '{res_item[0]}' slot '{res_item[1]}' cannot be simultaneously available and busy.")

        # Check if any goal condition directly contradicts a negative constraint
        goal_tuples = {(g.predicate.lower(), tuple(g.arguments)) for g in proposal.goal_facts if not g.is_negated}
        for neg in proposal.negative_constraints:
            neg_tuple = (neg.predicate.lower(), tuple(neg.arguments))
            if neg_tuple in goal_tuples:
                errors.append(
                    f"Direct contradiction: goal condition '{neg.to_string()}' is simultaneously declared as a negative constraint."
                )

        # Validate first-class typed constraints
        for tc in getattr(proposal, "typed_constraints", []):
            if tc.action_name:
                act_schema = domain.get_action(tc.action_name) if hasattr(domain, "get_action") else None
                if not act_schema:
                    errors.append(f"Typed constraint specifies unsupported action '{tc.action_name}' for domain '{domain.name}'.")
                else:
                    if tc.arg_index is not None:
                        if tc.arg_index < 0 or tc.arg_index >= len(act_schema.parameters):
                            errors.append(
                                f"Typed constraint specifies invalid arg_index {tc.arg_index} for action '{tc.action_name}' "
                                f"(arity: {len(act_schema.parameters)})."
                            )
                    if tc.arguments:
                        if len(tc.arguments) != len(act_schema.parameters):
                            errors.append(
                                f"Typed constraint argument count mismatch for '{tc.action_name}': "
                                f"expected {len(act_schema.parameters)}, got {len(tc.arguments)}."
                            )
                        for a in tc.arguments:
                            if not registry.has_object(a):
                                errors.append(f"Typed constraint references unknown entity '{a}' in arguments.")
            if tc.entity and not registry.has_object(tc.entity):
                errors.append(f"Typed constraint references unknown entity '{tc.entity}'.")
            if tc.to_entity and not registry.has_object(tc.to_entity):
                errors.append(f"Typed constraint references unknown to_entity '{tc.to_entity}'.")
            if tc.from_entity and not registry.has_object(tc.from_entity):
                errors.append(f"Typed constraint references unknown from_entity '{tc.from_entity}'.")

        # Check domain default invariants on initial state if no prior errors
        if not errors and proposal.initial_facts:
            try:
                init_state_test = SymbolicState(
                    facts=[Fact.from_schema(f) for f in proposal.initial_facts if not f.is_negated],
                    objects=registry.get_all_objects(),
                )
                for inv in getattr(domain, "default_invariants", []):
                    sat, inv_msg = inv.check(init_state_test)
                    if not sat:
                        errors.append(f"Domain invariant violation in initial state: {inv_msg}")
            except Exception:
                pass

        if errors:
            status = ValidationStatus.CONTRADICTION if any(
                k in errors[0] for k in ("Contradiction", "Contradictory", "Mutex violation", "simultaneously", "invariant violation")
            ) else ValidationStatus.SCHEMA_ERROR
            if any("Unknown entity" in e for e in errors):
                status = ValidationStatus.UNKNOWN_ENTITY
            elif any("Arity mismatch" in e for e in errors):
                status = ValidationStatus.ARITY_MISMATCH
            elif any("Type mismatch" in e for e in errors):
                status = ValidationStatus.TYPE_MISMATCH
            elif any("Unsupported predicate" in e or "unsupported action" in e for e in errors):
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
        # Enforce physical consistency: if on(x, y) holds, y is covered and cannot be clear(y)
        covered_objects = {
            f.arguments[1]
            for f in init_facts
            if f.predicate.lower() == "on" and len(f.arguments) >= 2 and not f.is_negated
        }
        consistent_facts = [
            f for f in init_facts
            if not (f.predicate.lower() == "clear" and f.arguments and f.arguments[0] in covered_objects and not f.is_negated)
        ]
        init_state = SymbolicState(facts=consistent_facts, objects=reg.get_all_objects())

        goal_facts = [Fact.from_schema(g) for g in proposal.goal_facts]

        # Convert negative constraints to Invariants or HardConstraints
        invariants: List[Invariant] = list(getattr(domain, "default_invariants", []))
        hard_constraints: List[HardConstraint] = []

        for inv_fact in getattr(proposal, "invariants", []):
            fact_cond = Fact.from_schema(inv_fact)
            if inv_fact.is_negated:
                invariants.append(NegativeFactInvariant(fact_cond.positive_version()))

        # 1. Process first-class typed constraints
        for tc in getattr(proposal, "typed_constraints", []):
            if tc.constraint_type == TaskConstraintType.FORBID_STATE_FACT and tc.state_fact:
                fact_cond = Fact.from_schema(tc.state_fact)
                invariants.append(
                    NegativeFactInvariant(
                        fact_cond.positive_version(),
                        description=tc.description or f"Forbidden state: {fact_cond.to_string()}",
                    )
                )
            elif tc.constraint_type == TaskConstraintType.FORBID_ACTION and tc.action_name:
                hard_constraints.append(
                    ForbidActionConstraint(
                        tc.action_name,
                        description=tc.description or f"Action '{tc.action_name}' strictly forbidden.",
                    )
                )
            elif tc.constraint_type == TaskConstraintType.FORBID_ACTION_BINDING:
                if tc.arguments and tc.action_name:
                    hard_constraints.append(
                        ForbidActionExactBindingConstraint(
                            tc.action_name,
                            tc.arguments,
                            description=tc.description or f"Action '{tc.action_name}({', '.join(tc.arguments)})' forbidden.",
                        )
                    )
                elif tc.entity and tc.action_name:
                    hard_constraints.append(
                        ForbidActionBindingConstraint(
                            tc.action_name,
                            tc.entity,
                            arg_index=tc.arg_index,
                            description=tc.description or f"Action '{tc.action_name}' with entity '{tc.entity}' forbidden.",
                        )
                    )
            elif tc.constraint_type == TaskConstraintType.FORBID_TRANSITION:
                if tc.action_name and tc.to_entity and tc.arg_index is not None:
                    hard_constraints.append(
                        ForbidTransitionConstraint(
                            tc.action_name,
                            tc.to_entity,
                            tc.arg_index,
                            from_entity=tc.from_entity,
                            description=tc.description or f"Transition via '{tc.action_name}' to '{tc.to_entity}' forbidden.",
                        )
                    )
                if tc.state_fact:
                    fact_cond = Fact.from_schema(tc.state_fact)
                    invariants.append(
                        NegativeFactInvariant(
                            fact_cond.positive_version(),
                            description=tc.description or f"Forbidden transition state: {fact_cond.to_string()}",
                        )
                    )

        # 2. Backwards-compatible negative_constraints conversion
        for neg in proposal.negative_constraints:
            fact_cond = Fact.from_schema(neg)
            invariants.append(
                NegativeFactInvariant(
                    fact_cond.positive_version(),
                    description=f"Negative constraint: {fact_cond.to_string()} must never hold.",
                )
            )
            # If no typed constraints were supplied, deterministically infer action-level constraints
            if not getattr(proposal, "typed_constraints", []):
                p_name = fact_cond.predicate.lower()
                if p_name == "holding" and fact_cond.arguments and domain.name in ("blocks_world", "blocks"):
                    hard_constraints.append(ForbidActionBindingConstraint("pick_up", fact_cond.arguments[0], arg_index=0))
                    hard_constraints.append(ForbidActionBindingConstraint("unstack", fact_cond.arguments[0], arg_index=0))
                elif p_name == "on" and len(fact_cond.arguments) >= 2 and domain.name in ("blocks_world", "blocks"):
                    hard_constraints.append(ForbidActionExactBindingConstraint("stack", [fact_cond.arguments[0], fact_cond.arguments[1]]))
                elif p_name == "at" and len(fact_cond.arguments) >= 2 and domain.name in ("grid_world", "grid"):
                    hard_constraints.append(ForbidTransitionConstraint("move", fact_cond.arguments[1], arg_index=2))
                elif p_name == "deployed_to" and len(fact_cond.arguments) >= 2 and domain.name == "software_workflow":
                    hard_constraints.append(ForbidActionBindingConstraint("deploy", fact_cond.arguments[1], arg_index=1))

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
