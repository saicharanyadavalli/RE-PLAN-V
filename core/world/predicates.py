"""Predicates and Ground Facts for the symbolic world model."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple
from core.contracts import FactSchema
from core.world.types import ObjectRegistry


class PredicateDefinition:
    """Formal definition of a relation / predicate symbol."""

    def __init__(
        self,
        name: str,
        arg_types: Sequence[str],
        is_static: bool = False,
        description: str = "",
    ) -> None:
        self.name = name.strip().lower()
        self.arg_types = tuple(t.strip().lower() for t in arg_types)
        self.arity = len(self.arg_types)
        self.is_static = is_static
        self.description = description

    def validate_arguments(self, args: Sequence[str], registry: ObjectRegistry) -> Tuple[bool, Optional[str]]:
        if len(args) != self.arity:
            return False, f"Predicate '{self.name}' expects {self.arity} arguments, got {len(args)}: {args}"

        for idx, (arg_name, expected_type) in enumerate(zip(args, self.arg_types)):
            if not registry.has_object(arg_name):
                return False, f"Unknown entity '{arg_name}' for predicate '{self.name}' at position {idx}"
            obj_type = registry.get_type_of(arg_name)
            if obj_type is None or not registry.hierarchy.is_subtype(obj_type, expected_type):
                return False, f"Type mismatch for '{arg_name}': expected '{expected_type}', got '{obj_type}'"

        return True, None

    def __repr__(self) -> str:
        types_str = ", ".join(self.arg_types)
        return f"{self.name}({types_str})"


class Fact:
    """An immutable, hashable, ground atom in the symbolic universe."""

    __slots__ = ("_predicate", "_arguments", "_is_negated", "_hash")

    def __init__(self, predicate: str, arguments: Sequence[str], is_negated: bool = False) -> None:
        self._predicate = predicate.strip().lower()
        self._arguments = tuple(arg.strip() for arg in arguments)
        self._is_negated = bool(is_negated)
        self._hash = hash((self._predicate, self._arguments, self._is_negated))

    @property
    def predicate(self) -> str:
        return self._predicate

    @property
    def arguments(self) -> Tuple[str, ...]:
        return self._arguments

    @property
    def arity(self) -> int:
        return len(self._arguments)

    @property
    def is_negated(self) -> bool:
        return self._is_negated

    def positive_version(self) -> Fact:
        if not self._is_negated:
            return self
        return Fact(self._predicate, self._arguments, is_negated=False)

    def negated_version(self) -> Fact:
        return Fact(self._predicate, self._arguments, is_negated=not self._is_negated)

    def to_schema(self) -> FactSchema:
        return FactSchema(
            predicate=self._predicate,
            arguments=self._arguments,
            is_negated=self._is_negated,
        )

    @classmethod
    def from_schema(cls, schema: FactSchema) -> Fact:
        return cls(
            predicate=schema.predicate,
            arguments=schema.arguments,
            is_negated=schema.is_negated,
        )

    def to_string(self) -> str:
        args_str = ", ".join(self._arguments)
        base = f"{self._predicate}({args_str})"
        return f"not({base})" if self._is_negated else base

    def __str__(self) -> str:
        return self.to_string()

    def __repr__(self) -> str:
        return f"Fact({self.to_string()})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Fact):
            return False
        return (
            self._predicate == other._predicate
            and self._arguments == other._arguments
            and self._is_negated == other._is_negated
        )

    def __hash__(self) -> int:
        return self._hash

    def __lt__(self, other: Fact) -> bool:
        """Deterministic ordering for sorting facts."""
        return (self._predicate, self._arguments, self._is_negated) < (
            other._predicate,
            other._arguments,
            other._is_negated,
        )
