"""Ground instantiated actions."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple
from core.contracts import GroundActionSchema
from core.world.predicates import Fact
from core.world.state import SymbolicState


class GroundAction:
    """An instantiated action with all parameters bound to concrete objects."""

    __slots__ = (
        "name",
        "arguments",
        "preconditions",
        "add_effects",
        "del_effects",
        "cost",
        "parent_schema",
        "_hash",
    )

    def __init__(
        self,
        name: str,
        arguments: Sequence[str],
        preconditions: Sequence[Fact],
        add_effects: Sequence[Fact],
        del_effects: Sequence[Fact],
        cost: float = 1.0,
        parent_schema: Optional[Any] = None,
    ) -> None:
        self.name = name.strip().lower()
        self.arguments = tuple(arg.strip() for arg in arguments)
        self.preconditions = tuple(preconditions)
        self.add_effects = tuple(add_effects)
        self.del_effects = tuple(del_effects)
        self.cost = float(cost)
        self.parent_schema = parent_schema
        self._hash = hash((self.name, self.arguments))

    def is_applicable(self, state: SymbolicState) -> Tuple[bool, Optional[Fact]]:
        """Checks if all preconditions hold in the given state. Returns (is_applicable, first_unmet_precondition)."""
        for pre in self.preconditions:
            if not state.holds(pre):
                return False, pre
        return True, None

    def to_schema(self) -> GroundActionSchema:
        return GroundActionSchema(
            name=self.name,
            arguments=self.arguments,
            cost=self.cost,
        )

    @classmethod
    def from_schema(
        cls,
        schema: GroundActionSchema,
        preconditions: Sequence[Fact] = (),
        add_effects: Sequence[Fact] = (),
        del_effects: Sequence[Fact] = (),
    ) -> GroundAction:
        return cls(
            name=schema.name,
            arguments=schema.arguments,
            preconditions=preconditions,
            add_effects=add_effects,
            del_effects=del_effects,
            cost=schema.cost,
        )

    def to_string(self) -> str:
        args_str = ", ".join(self.arguments)
        return f"{self.name}({args_str})"

    def __str__(self) -> str:
        return self.to_string()

    def __repr__(self) -> str:
        return f"GroundAction({self.to_string()}, cost={self.cost})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, GroundAction):
            return False
        return self.name == other.name and self.arguments == other.arguments

    def __hash__(self) -> int:
        return self._hash

    def __lt__(self, other: GroundAction) -> bool:
        return (self.name, self.arguments) < (other.name, other.arguments)
