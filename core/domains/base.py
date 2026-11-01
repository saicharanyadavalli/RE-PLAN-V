"""Generic Domain Base Class and Contract for RE-PLAN-V.

Every planning domain (Blocks World, Grid World, Household Robotics,
Warehouse, Scheduling, Software Automation) inherits from BaseDomain.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional, Sequence, Tuple

from core.actions.definition import ActionDefinition
from core.actions.generator import LegalActionGenerator
from core.actions.instantiation import GroundAction
from core.actions.transition import apply_transition
from core.world.constraints import Invariant
from core.world.predicates import Fact, PredicateDefinition
from core.world.state import SymbolicState
from core.world.types import ObjectRegistry, TypeHierarchy


class BaseDomain:
    """Abstract base domain providing authoritative action schemas, state-transition

    semantics, invariant checking, and canonical serialization.
    """

    def __init__(
        self,
        domain_id: str,
        name: str,
        version: str = "1.0.0",
        description: str = "",
        type_hierarchy: Optional[TypeHierarchy] = None,
        predicates: Sequence[PredicateDefinition] = (),
        actions: Sequence[ActionDefinition] = (),
        default_invariants: Sequence[Invariant] = (),
        task_examples: Sequence[Dict[str, Any]] = (),
        supported_patterns: Sequence[str] = (),
        unsupported_features: Sequence[str] = (),
    ) -> None:
        self.domain_id = domain_id.strip().lower()
        self.name = name.strip()
        self.version = version.strip()
        self.description = description.strip()
        self.type_hierarchy = type_hierarchy or TypeHierarchy()
        self.predicates = {p.name: p for p in predicates}
        self.actions = {a.name: a for a in actions}
        self.default_invariants = list(default_invariants)
        self.task_examples = list(task_examples)
        self.supported_patterns = list(supported_patterns)
        self.unsupported_features = list(unsupported_features)

    def get_action(self, name: str) -> Optional[ActionDefinition]:
        return self.actions.get(name.strip().lower())

    def get_all_actions(self) -> List[ActionDefinition]:
        return list(self.actions.values())

    def applicable_actions(
        self, state: SymbolicState, registry: ObjectRegistry
    ) -> List[GroundAction]:
        """Generates all applicable ground actions for the current state under this domain."""
        generator = LegalActionGenerator(list(self.actions.values()), registry)
        return generator.get_applicable_actions(state)

    def apply_action(
        self, state: SymbolicState, action: GroundAction
    ) -> Tuple[SymbolicState, Optional[str]]:
        """Applies an action to a state under authoritative STRIPS semantics."""
        return apply_transition(state, action)

    def check_invariants(self, state: SymbolicState) -> Tuple[bool, Optional[str]]:
        """Checks whether the given state satisfies all domain-level invariants."""
        for inv in self.default_invariants:
            ok, msg = inv.check(state)
            if not ok:
                return False, msg
        return True, None

    def validate_initial_state(
        self, state: SymbolicState, registry: ObjectRegistry
    ) -> List[str]:
        """Validates that initial state facts conform to registered predicates and objects."""
        errors: List[str] = []
        for fact in state.facts:
            pred_def = self.predicates.get(fact.predicate)
            if not pred_def:
                errors.append(f"Unknown predicate '{fact.predicate}' in initial state.")
            elif len(fact.arguments) != pred_def.arity:
                errors.append(
                    f"Arity mismatch for '{fact.predicate}': expected {pred_def.arity}, got {len(fact.arguments)}."
                )
        return errors

    def validate_goal(
        self, goals: Sequence[Fact], registry: ObjectRegistry
    ) -> List[str]:
        """Validates goal conditions."""
        errors: List[str] = []
        for goal in goals:
            pred_def = self.predicates.get(goal.predicate)
            if not pred_def:
                errors.append(f"Unknown predicate '{goal.predicate}' in goal condition.")
            elif len(goal.arguments) != pred_def.arity:
                errors.append(
                    f"Arity mismatch for goal '{goal.predicate}': expected {pred_def.arity}, got {len(goal.arguments)}."
                )
        return errors

    def canonical_state_key(self, state: SymbolicState) -> str:
        """Returns a deterministic SHA-256 hex digest representing the unique semantic state.

        Sorts facts canonically and joins them into a stable string before hashing.
        """
        sorted_facts = sorted([f.to_string() for f in state.facts])
        payload = f"{self.domain_id}::" + "|".join(sorted_facts)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def render_state_summary(self, state: SymbolicState) -> str:
        """Produces a human-readable 1-line or concise summary of the state facts."""
        sorted_facts = sorted([f.to_string() for f in state.facts])
        return f"[{self.name}] {len(sorted_facts)} facts: " + ", ".join(sorted_facts[:5]) + ("..." if len(sorted_facts) > 5 else "")

    def to_dict(self) -> Dict[str, Any]:
        """Serializes domain metadata for the API and frontend Domain Studio."""
        return {
            "domain_id": self.domain_id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "entity_types": list(self.type_hierarchy.get_all_types()),
            "predicates": [
                {"name": p.name, "arity": p.arity, "arg_types": p.arg_types, "is_static": p.is_static}
                for p in self.predicates.values()
            ],
            "actions": [
                {
                    "name": a.name,
                    "parameters": [{"name": p.name, "type_name": p.type_name} for p in a.parameters],
                    "cost": a.cost,
                    "description": a.description,
                }
                for a in self.actions.values()
            ],
            "default_invariants_count": len(self.default_invariants),
            "task_examples": self.task_examples,
            "supported_patterns": self.supported_patterns,
            "unsupported_features": self.unsupported_features,
        }
