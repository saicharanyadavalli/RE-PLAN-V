"""Formal definition of a planning problem instance."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple
from core.contracts import BenchmarkInstanceSchema, FactSchema
from core.world.constraints import HardConstraint, Invariant
from core.world.predicates import Fact
from core.world.state import SymbolicState
from core.world.types import ObjectRegistry, TypeHierarchy


class SymbolicProblem:
    """Encapsulates a full symbolic planning problem instance."""

    def __init__(
        self,
        name: str,
        domain_name: str,
        registry: ObjectRegistry,
        initial_state: SymbolicState,
        goal_conditions: Sequence[Fact],
        invariants: Optional[Sequence[Invariant]] = None,
        hard_constraints: Optional[Sequence[HardConstraint]] = None,
        description: str = "",
    ) -> None:
        self.name = name
        self.domain_name = domain_name
        self.registry = registry
        self.initial_state = initial_state
        self.goal_conditions = tuple(goal_conditions)
        self.invariants = tuple(invariants or [])
        self.hard_constraints = tuple(hard_constraints or [])
        self.description = description

    def is_goal_satisfied(self, state: SymbolicState) -> bool:
        return state.satisfies_all(self.goal_conditions)

    def find_unmet_goals(self, state: SymbolicState) -> List[Fact]:
        return state.find_unmet_conditions(self.goal_conditions)

    def check_invariants(self, state: SymbolicState) -> Tuple[bool, Optional[str]]:
        for inv in self.invariants:
            ok, msg = inv.check(state)
            if not ok:
                return False, msg
        return True, None

    def check_hard_constraints(
        self, state: SymbolicState, action_name: str, action_args: Sequence[str]
    ) -> Tuple[bool, Optional[str]]:
        for hc in self.hard_constraints:
            ok, msg = hc.check_action(state, action_name, action_args)
            if not ok:
                return False, msg
        return True, None

    def validate(self) -> List[str]:
        """Validates consistency of the problem definition."""
        errors: List[str] = []

        # 1. Check initial state against invariants
        ok, msg = self.check_invariants(self.initial_state)
        if not ok and msg:
            errors.append(f"Initial state violates invariant: {msg}")

        # 2. Check entities in goals exist in registry
        for g in self.goal_conditions:
            for arg in g.arguments:
                if not self.registry.has_object(arg):
                    errors.append(f"Goal condition {g} references unknown entity '{arg}'")

        # 3. Check entities in initial state exist in registry
        for f in self.initial_state.facts:
            for arg in f.arguments:
                if not self.registry.has_object(arg):
                    errors.append(f"Initial state fact {f} references unknown entity '{arg}'")

        return errors

    def to_schema(self) -> BenchmarkInstanceSchema:
        return BenchmarkInstanceSchema(
            instance_id=self.name,
            domain=self.domain_name,
            name=self.name,
            objects=self.registry.get_all_objects(),
            initial_facts=[f.to_schema() for f in sorted(self.initial_state.facts)],
            goal_facts=[g.to_schema() for g in self.goal_conditions],
            description=self.description,
        )

    def __repr__(self) -> str:
        return f"SymbolicProblem(name='{self.name}', domain='{self.domain_name}', goals={self.goal_conditions})"
