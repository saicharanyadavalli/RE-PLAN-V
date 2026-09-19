"""Horn-clause rules for knowledge representation and reasoning."""

from __future__ import annotations

from typing import List, Sequence, Tuple
from core.world.predicates import Fact


class Rule:
    """A definite Horn clause: Head :- Body_1, Body_2, ..., Body_n."""

    def __init__(self, head: Fact, body: Sequence[Fact], name: str = "") -> None:
        self.head = head
        self.body = tuple(body)
        self.name = name or f"rule_{head.predicate}"

    def __repr__(self) -> str:
        body_str = ", ".join(f.to_string() for f in self.body)
        return f"{self.head.to_string()} :- {body_str}"

    def __str__(self) -> str:
        return self.__repr__()
