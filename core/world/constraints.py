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
        if self.prohibited_actions and act in self.prohibited_actions and self.protected_entity in action_args:
            return False, f"Hard constraint violation: action '{action_name}' on protected entity '{self.protected_entity}' is strictly forbidden."
        return True, None


class ForbidActionConstraint(HardConstraint):
    """Prohibits any execution of a specific action name regardless of arguments."""

    def __init__(self, forbidden_action: str, description: str = "") -> None:
        act = forbidden_action.strip().lower()
        super().__init__(name=f"forbid_action_{act}", description=description)
        self.forbidden_action = act

    def check_action(self, state: SymbolicState, action_name: str, action_args: Sequence[str]) -> Tuple[bool, Optional[str]]:
        if action_name.strip().lower() == self.forbidden_action:
            return False, f"Hard constraint violation: action '{action_name}' is strictly forbidden."
        return True, None


class ForbidActionBindingConstraint(HardConstraint):
    """Prohibits executing an action when a specific entity is bound to its arguments."""

    def __init__(
        self,
        forbidden_action: str,
        entity: str,
        arg_index: Optional[int] = None,
        description: str = "",
    ) -> None:
        act = forbidden_action.strip().lower()
        ent = entity.strip()
        name = f"forbid_binding_{act}_{ent}" if arg_index is None else f"forbid_binding_{act}_{ent}_at_{arg_index}"
        super().__init__(name=name, description=description)
        self.forbidden_action = act
        self.entity = ent
        self.arg_index = arg_index

    def check_action(self, state: SymbolicState, action_name: str, action_args: Sequence[str]) -> Tuple[bool, Optional[str]]:
        if action_name.strip().lower() == self.forbidden_action:
            if self.arg_index is not None:
                if 0 <= self.arg_index < len(action_args) and action_args[self.arg_index] == self.entity:
                    return False, f"Hard constraint violation: action '{action_name}' with '{self.entity}' at position {self.arg_index} is strictly forbidden."
            else:
                if self.entity in action_args:
                    return False, f"Hard constraint violation: action '{action_name}' with entity '{self.entity}' is strictly forbidden."
        return True, None


class ForbidActionExactBindingConstraint(HardConstraint):
    """Prohibits executing an action with exact ordered argument values (e.g. stack(green, yellow))."""

    def __init__(
        self,
        forbidden_action: str,
        arguments: Sequence[str],
        description: str = "",
    ) -> None:
        act = forbidden_action.strip().lower()
        args_tuple = tuple(a.strip() for a in arguments)
        name = f"forbid_exact_{act}_{'_'.join(args_tuple)}"
        super().__init__(name=name, description=description)
        self.forbidden_action = act
        self.forbidden_args = args_tuple

    def check_action(self, state: SymbolicState, action_name: str, action_args: Sequence[str]) -> Tuple[bool, Optional[str]]:
        if action_name.strip().lower() == self.forbidden_action:
            if tuple(action_args) == self.forbidden_args:
                return (
                    False,
                    f"Hard constraint violation: exact action '{action_name}({', '.join(action_args)})' is strictly forbidden.",
                )
        return True, None


class ForbidTransitionConstraint(HardConstraint):
    """Prohibits transitions targeting a forbidden destination or state (e.g. entering cell_trap or deploying to prod)."""

    def __init__(
        self,
        forbidden_action: str,
        to_entity: str,
        arg_index: int,
        from_entity: Optional[str] = None,
        description: str = "",
    ) -> None:
        act = forbidden_action.strip().lower()
        dst = to_entity.strip()
        name = f"forbid_transition_{act}_to_{dst}"
        super().__init__(name=name, description=description)
        self.forbidden_action = act
        self.to_entity = dst
        self.arg_index = arg_index
        self.from_entity = from_entity.strip() if from_entity else None

    def check_action(self, state: SymbolicState, action_name: str, action_args: Sequence[str]) -> Tuple[bool, Optional[str]]:
        if action_name.strip().lower() == self.forbidden_action:
            if 0 <= self.arg_index < len(action_args):
                if action_args[self.arg_index] == self.to_entity:
                    if self.from_entity is None:
                        return False, f"Hard constraint violation: transition via '{action_name}' to '{self.to_entity}' is strictly forbidden."
                    elif self.from_entity in action_args:
                        return False, f"Hard constraint violation: transition via '{action_name}' from '{self.from_entity}' to '{self.to_entity}' is strictly forbidden."
        return True, None
