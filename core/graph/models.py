"""Data models and schemas for the Complete State-Space Graph Explorer (Model B)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class GraphNode(BaseModel):
    """Represents a unique semantic symbolic state in the reachable graph."""
    node_id: str
    facts: List[str]
    depth: int = 0
    is_initial: bool = False
    is_goal: bool = False
    is_dead_end: bool = False
    is_boundary: bool = False
    expanded: bool = False
    partially_expanded: bool = False
    summary: str = ""
    g_cost: Optional[float] = None
    h_cost: Optional[float] = None
    f_cost: Optional[float] = None


class GraphEdge(BaseModel):
    """Represents an authoritative directed transition between two symbolic states."""
    edge_id: str
    source_id: str
    target_id: str
    action_name: str
    action_args: List[str]
    action_label: str
    cost: float = 1.0
    is_plan_edge: bool = False
    is_repaired_edge: bool = False


class GraphStats(BaseModel):
    """Summary statistics for the enumerated state-space graph."""
    total_nodes: int = 0
    total_edges: int = 0
    initial_node_id: str = ""
    goal_node_ids: List[str] = Field(default_factory=list)
    dead_end_node_ids: List[str] = Field(default_factory=list)
    max_depth: int = 0
    is_complete: bool = False
    truncation_reason: Optional[str] = None
    enumeration_time_ms: float = 0.0
    duplicate_states_pruned: int = 0
    cycles_detected: int = 0


class ReachableStateGraph(BaseModel):
    """Complete reachable state space artifact computed from symbolic initial state."""
    graph_id: str
    domain_id: str
    problem_name: str
    nodes: Dict[str, GraphNode] = Field(default_factory=dict)
    edges: List[GraphEdge] = Field(default_factory=list)
    stats: GraphStats = Field(default_factory=GraphStats)

    def to_cytoscape(self) -> Dict[str, Any]:
        """Converts graph into Cytoscape.js format for high-performance frontend visualization."""
        cy_elements = []
        # Nodes
        for n in self.nodes.values():
            classes = []
            if n.is_initial:
                classes.append("initial")
            if n.is_goal:
                classes.append("goal")
            if n.is_dead_end:
                classes.append("dead_end")
            if n.is_boundary or n.partially_expanded:
                classes.append("boundary")

            cy_elements.append({
                "data": {
                    "id": n.node_id,
                    "label": f"S{n.depth}: {n.summary[:24]}" if n.summary else n.node_id[:8],
                    "depth": n.depth,
                    "is_initial": n.is_initial,
                    "is_goal": n.is_goal,
                    "is_dead_end": n.is_dead_end,
                    "is_boundary": n.is_boundary or n.partially_expanded,
                    "partially_expanded": n.partially_expanded,
                    "expanded": n.expanded,
                    "facts": n.facts,
                },
                "classes": " ".join(classes),
            })

        # Edges
        for e in self.edges:
            cy_elements.append({
                "data": {
                    "id": e.edge_id,
                    "source": e.source_id,
                    "target": e.target_id,
                    "label": e.action_label,
                    "cost": e.cost,
                    "is_plan_edge": e.is_plan_edge,
                    "is_repaired_edge": e.is_repaired_edge,
                },
                "classes": "plan_edge" if e.is_plan_edge else "regular_edge",
            })

        return {
            "format": "cytoscape",
            "graph_id": self.graph_id,
            "domain_id": self.domain_id,
            "problem_name": self.problem_name,
            "stats": self.stats.model_dump(),
            "elements": cy_elements,
        }
