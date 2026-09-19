"""Action definitions with typed parameters, preconditions, and effects."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple
from core.contracts import ActionDefSchema, FactSchema
from core.world.predicates import Fact


class ActionParameter:
    """A typed parameter in an action schema (e.g., '?b: block')."""

    def __init__(self, name: str, type_name: str = "object") -> None:
        self.name = name.strip() if name.startswith("?") else f"?{name.strip()}"
        self.type_name = type_name.strip().lower()

    def __repr__(self) -> str:
        return f"{self.name}:{self.type_name}"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ActionParameter):
            return False
        return self.name == other.name and self.type_name == other.type_name

    def __hash__(self) -> int:
        return hash((self.name, self.type_name))


class ActionDefinition:
    """Lifted action operator with parameter variables and formal STRIPS semantics."""

    def __init__(
        self,
        name: str,
        parameters: Sequence[ActionParameter],
        preconditions: Sequence[Fact],
        add_effects: Sequence[Fact],
        del_effects: Sequence[Fact],
        cost: float = 1.0,
        description: str = "",
    ) -> None:
        self.name = name.strip().lower()
        self.parameters = tuple(parameters)
        self.preconditions = tuple(preconditions)
        self.add_effects = tuple(add_effects)
        self.del_effects = tuple(del_effects)
        self.cost = float(cost)
        self.description = description

    def instantiate(self, binding: Dict[str, str]) -> "GroundAction":
        """Instantiates lifted action into a concrete GroundAction using parameter binding."""
        from core.actions.instantiation import GroundAction

        # Helper to substitute variable arguments with bound object names
        def ground_fact(f: Fact) -> Fact:
            ground_args = [binding.get(arg, arg) for arg in f.arguments]
            return Fact(f.predicate, ground_args, is_negated=f.is_negated)

        ground_pre = tuple(ground_fact(f) for f in self.preconditions)
        ground_adds = tuple(ground_fact(f) for f in self.add_effects)
        ground_dels = tuple(ground_fact(f) for f in self.del_effects)
        args = tuple(binding[p.name] for p in self.parameters)

        return GroundAction(
            name=self.name,
            arguments=args,
            preconditions=ground_pre,
            add_effects=ground_adds,
            del_effects=ground_dels,
            cost=self.cost,
            parent_schema=self,
        )

    def to_schema(self) -> ActionDefSchema:
        return ActionDefSchema(
            name=self.name,
            parameters=[(p.name, p.type_name) for p in self.parameters],
            preconditions=[p.to_schema() for p in self.preconditions],
            add_effects=[a.to_schema() for a in self.add_effects],
            del_effects=[d.to_schema() for d in self.del_effects],
            cost=self.cost,
        )

    def __repr__(self) -> str:
        params_str = ", ".join(repr(p) for p in self.parameters)
        return f"ActionDef({self.name}({params_str}), cost={self.cost})"
