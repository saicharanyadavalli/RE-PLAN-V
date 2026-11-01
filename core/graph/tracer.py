"""Algorithm search tracing and solution path highlighting."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, Field

from core.graph.models import ReachableStateGraph


class SearchStepRecord(BaseModel):
    step_index: int
    node_id: str
    action_from_parent: Optional[str] = None
    g_cost: float = 0.0
    h_cost: float = 0.0
    f_cost: float = 0.0
    frontier_size: int = 0


class AlgorithmSearchTrace(BaseModel):
    algorithm: str
    expanded_sequence: List[str] = Field(default_factory=list)
    steps: List[SearchStepRecord] = Field(default_factory=list)
    solution_path_node_ids: List[str] = Field(default_factory=list)
    solution_path_edge_ids: List[str] = Field(default_factory=list)
    nodes_generated: int = 0
    nodes_expanded: int = 0
    max_frontier_size: int = 0
    search_time_ms: float = 0.0


class AlgorithmSearchTracer:
    """Records search trace events independently from complete graph enumeration."""

    def __init__(self, algorithm: str = "A*") -> None:
        self.algorithm = algorithm
        self.trace = AlgorithmSearchTrace(algorithm=algorithm)

    def record_expansion(
        self,
        node_id: str,
        action_from_parent: Optional[str] = None,
        g_cost: float = 0.0,
        h_cost: float = 0.0,
        f_cost: float = 0.0,
        frontier_size: int = 0,
    ) -> None:
        step_idx = len(self.trace.steps) + 1
        rec = SearchStepRecord(
            step_index=step_idx,
            node_id=node_id,
            action_from_parent=action_from_parent,
            g_cost=g_cost,
            h_cost=h_cost,
            f_cost=f_cost,
            frontier_size=frontier_size,
        )
        self.trace.steps.append(rec)
        self.trace.expanded_sequence.append(node_id)
        self.trace.nodes_expanded += 1
        if frontier_size > self.trace.max_frontier_size:
            self.trace.max_frontier_size = frontier_size

    def overlay_on_graph(self, graph: ReachableStateGraph) -> ReachableStateGraph:
        """Overlays search metrics (g, h, f) and highlights solution edges onto the graph."""
        # Annotate nodes
        for step in self.trace.steps:
            if step.node_id in graph.nodes:
                graph.nodes[step.node_id].g_cost = step.g_cost
                graph.nodes[step.node_id].h_cost = step.h_cost
                graph.nodes[step.node_id].f_cost = step.f_cost

        # Mark solution edges
        sol_set = set(self.trace.solution_path_edge_ids)
        for e in graph.edges:
            if e.edge_id in sol_set:
                e.is_plan_edge = True

        return graph
