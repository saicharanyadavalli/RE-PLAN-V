"""Invariants and hard safety constraints for the symbolic world model."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple
from core.contracts import FactSchema
from core.world.predicates import Fact
from core.world.state import SymbolicState


class Invariant(ABC):
    """A global safety property that must hold in every reachable state."""

    def __init__(self, name: str, description: str = "") -> None:
        self.name = name
        self.description = description

    @abstractmethod
    def check(self, state: SymbolicState) -> Tuple[bool, Optional[str]]:
        """Returns (is_satisfied, violation_message)."""
        pass


class NegativeFactInvariant(Invariant):
    """Enforces that a specific condition must NEVER hold in any state."""

    def __init__(self, forbidden_fact: Fact, description: str = "") -> None:
        name = f"never_{forbidden_fact.to_string()}"
        super().__init__(name=name, description=description)
        self.forbidden_fact = forbidden_fact

    def check(self, state: SymbolicState) -> Tuple[bool, Optional[str]]:
        if state.holds(self.forbidden_fact):
            return False, f"Invariant violation '{self.name}': forbidden condition {self.forbidden_fact} holds in state."
        return True, None


class FunctionalDependencyInvariant(Invariant):
    """Enforces single-valued functional dependency (e.g., each block can only be ON one object)."""

    def __init__(self, predicate_name: str, key_arg_idx: int = 0, value_arg_idx: int = 1) -> None:
        super().__init__(name=f"functional_{predicate_name}_{key_arg_idx}->{value_arg_idx}")
        self.predicate_name = predicate_name.strip().lower()
        self.key_arg_idx = key_arg_idx
        self.value_arg_idx = value_arg_idx

    def check(self, state: SymbolicState) -> Tuple[bool, Optional[str]]:
        facts = state.get_facts_for_predicate(self.predicate_name)
        seen: Dict[str, str] = {}
        for f in facts:
            if len(f.arguments) > max(self.key_arg_idx, self.value_arg_idx):
                k = f.arguments[self.key_arg_idx]
                v = f.arguments[self.value_arg_idx]
                if k in seen and seen[k] != v:
                    return (
                        False,
                        f"Functional dependency violated for {self.predicate_name}: "
                        f"key '{k}' mapped to multiple values ('{seen[k]}' and '{v}')",
                    )
                seen[k] = v
        return True, None


class HardConstraint(ABC):
    """Action or transition-level constraint (e.g., never execute an action touching a fragile item)."""

    def __init__(self, name: str, description: str = "") -> None:
        self.name = name
        self.description = description

    @abstractmethod
    def check_action(self, state: SymbolicState, action_name: str, action_args: Sequence[str]) -> Tuple[bool, Optional[str]]:
        pass


class ProhibitedEntityActionConstraint(HardConstraint):
    """Prohibits executing specified actions on designated protected entities."""

    def __init__(self, protected_entity: str, prohibited_actions: Sequence[str], description: str = "") -> None:
        name = f"protect_{protected_entity}"
        super().__init__(name=name, description=description)
        self.protected_entity = protected_entity.strip()
        self.prohibited_actions = set(a.strip().lower() for a in prohibited_actions)

    def check_action(self, state: SymbolicState, action_name: str, action_args: Sequence[str]) -> Tuple[bool, Optional[str]]:
        act = action_name.strip().lower()
        if (not self.prohibited_actions or act in self.prohibited_actions) and self.protected_entity in action_args:
            return False, f"Hard constraint violation: action '{action_name}' on protected entity '{self.protected_entity}' is strictly forbidden."
        return True, None
