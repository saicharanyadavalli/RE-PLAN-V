"""Authoritative SymbolicState for RE-PLAN-V.

State representation is immutable, hashable, deterministic, and supports closed-world reasoning.
"""

from __future__ import annotations

from typing import Any, Dict, FrozenSet, Iterable, List, Optional, Set, Tuple
from core.contracts import FactSchema, SymbolicStateSchema
from core.world.predicates import Fact


class SymbolicState:
    """Immutable state representation holding a closed-world frozenset of ground facts."""

    __slots__ = ("_facts", "_objects", "_step_index", "_hash")

    def __init__(
        self,
        facts: Iterable[Fact],
        objects: Optional[Dict[str, str]] = None,
        step_index: int = 0,
    ) -> None:
        # Filter to ensure only positive facts are stored in the state set
        positive_facts: Set[Fact] = set()
        for f in facts:
            if f.is_negated:
                continue
            positive_facts.add(f.positive_version())

        self._facts: FrozenSet[Fact] = frozenset(positive_facts)
        self._objects: Dict[str, str] = dict(objects or {})
        self._step_index: int = int(step_index)
        self._hash: int = hash((self._facts, self._step_index))

    @property
    def facts(self) -> FrozenSet[Fact]:
        return self._facts

    @property
    def objects(self) -> Dict[str, str]:
        return dict(self._objects)

    @property
    def step_index(self) -> int:
        return self._step_index

    def holds(self, fact: Fact) -> bool:
        """Determines truth of fact under Closed-World Assumption."""
        if fact.is_negated:
            return fact.positive_version() not in self._facts
        return fact in self._facts

    def satisfies_all(self, conditions: Iterable[Fact]) -> bool:
        """Returns True if every fact/condition in the iterable holds."""
        return all(self.holds(c) for c in conditions)

    def find_unmet_conditions(self, conditions: Iterable[Fact]) -> List[Fact]:
        """Returns list of conditions that do NOT hold in this state."""
        return [c for c in conditions if not self.holds(c)]

    def apply_effects(
        self,
        adds: Iterable[Fact],
        dels: Iterable[Fact],
        new_step_index: Optional[int] = None,
    ) -> SymbolicState:
        """Applies delete effects followed by add effects (STRIPS delete-before-add)."""
        current_set = set(self._facts)
        
        # 1. Apply deletes
        for d in dels:
            current_set.discard(d.positive_version())
            
        # 2. Apply adds
        for a in adds:
            if not a.is_negated:
                current_set.add(a.positive_version())
            else:
                # Adding a negated fact is equivalent to deleting the positive version
                current_set.discard(a.positive_version())

        step = self._step_index + 1 if new_step_index is None else new_step_index
        return SymbolicState(facts=current_set, objects=self._objects, step_index=step)

    def get_facts_for_predicate(self, predicate_name: str) -> List[Fact]:
        pred = predicate_name.strip().lower()
        return sorted([f for f in self._facts if f.predicate == pred])

    def to_sorted_tuple(self) -> Tuple[Fact, ...]:
        return tuple(sorted(self._facts))

    def to_schema(self) -> SymbolicStateSchema:
        return SymbolicStateSchema(
            facts=tuple(f.to_schema() for f in sorted(self._facts)),
            objects=dict(self._objects),
            step_index=self._step_index,
        )

    @classmethod
    def from_schema(cls, schema: SymbolicStateSchema) -> SymbolicState:
        facts = [Fact.from_schema(f) for f in schema.facts]
        return cls(facts=facts, objects=schema.objects, step_index=schema.step_index)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "facts": [f.to_string() for f in sorted(self._facts)],
            "objects": self._objects,
            "step_index": self._step_index,
        }

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SymbolicState):
            return False
        # Two states are semantically equivalent if their held facts and objects match
        return self._facts == other._facts and self._objects == other._objects

    def __hash__(self) -> int:
        return hash(self._facts)

    def __repr__(self) -> str:
        facts_str = ", ".join(f.to_string() for f in sorted(self._facts))
        return f"SymbolicState(step={self._step_index}, facts=[{facts_str}])"
