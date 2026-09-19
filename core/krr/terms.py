"""First-Order Logic terms, constants, variables, and substitutions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class Term(ABC):
    """Base class for terms in logic expressions."""

    @abstractmethod
    def is_variable(self) -> bool:
        pass

    @abstractmethod
    def is_constant(self) -> bool:
        pass


class Constant(Term):
    """A ground constant symbol (e.g., 'b1', 'table')."""

    __slots__ = ("name",)

    def __init__(self, name: str) -> None:
        self.name = str(name).strip()

    def is_variable(self) -> bool:
        return False

    def is_constant(self) -> bool:
        return True

    def __repr__(self) -> str:
        return self.name

    def __str__(self) -> str:
        return self.name

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Constant):
            return False
        return self.name == other.name

    def __hash__(self) -> int:
        return hash(self.name)


class Variable(Term):
    """A logical variable symbol (e.g., '?x', '?y')."""

    __slots__ = ("name",)

    def __init__(self, name: str) -> None:
        raw = str(name).strip()
        self.name = raw if raw.startswith("?") else f"?{raw}"

    def is_variable(self) -> bool:
        return True

    def is_constant(self) -> bool:
        return False

    def __repr__(self) -> str:
        return self.name

    def __str__(self) -> str:
        return self.name

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Variable):
            return False
        return self.name == other.name

    def __hash__(self) -> int:
        return hash(self.name)


def parse_term(s: str) -> Term:
    """Parses a string into Variable or Constant."""
    s = s.strip()
    return Variable(s) if s.startswith("?") else Constant(s)
