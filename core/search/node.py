"""Search node representation for graph search algorithms."""

from __future__ import annotations

from typing import List, Optional
from core.actions.instantiation import GroundAction
from core.world.state import SymbolicState


class SearchNode:
    """A node in the forward search tree / graph."""

    __slots__ = (
        "state",
        "parent",
        "action",
        "g_cost",
        "h_cost",
        "f_cost",
        "depth",
        "node_id",
    )

    _counter: int = 0

    def __init__(
        self,
        state: SymbolicState,
        parent: Optional[SearchNode] = None,
        action: Optional[GroundAction] = None,
        g_cost: float = 0.0,
        h_cost: float = 0.0,
    ) -> None:
        self.state = state
        self.parent = parent
        self.action = action
        self.g_cost = float(g_cost)
        self.h_cost = float(h_cost)
        self.f_cost = self.g_cost + self.h_cost
        self.depth = (parent.depth + 1) if parent else 0
        SearchNode._counter += 1
        self.node_id = SearchNode._counter

    def extract_plan(self) -> List[GroundAction]:
        """Reconstructs the plan actions from root to this node."""
        actions: List[GroundAction] = []
        curr: Optional[SearchNode] = self
        while curr and curr.action:
            actions.append(curr.action)
            curr = curr.parent
        actions.reverse()
        return actions

    def __lt__(self, other: SearchNode) -> bool:
        """Deterministic tie-breaking order for priority queues."""
        if abs(self.f_cost - other.f_cost) > 1e-9:
            return self.f_cost < other.f_cost
        if abs(self.h_cost - other.h_cost) > 1e-9:
            return self.h_cost < other.h_cost
        if self.depth != other.depth:
            return self.depth > other.depth  # Prefer deeper nodes on tie
        return self.node_id < other.node_id

    def __repr__(self) -> str:
        act_str = self.action.to_string() if self.action else "ROOT"
        return f"Node(act={act_str}, g={self.g_cost:.1f}, h={self.h_cost:.1f}, f={self.f_cost:.1f}, depth={self.depth})"
