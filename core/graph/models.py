"""Data models and schemas for the Complete State-Space Graph Explorer (Model B)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class GraphNode(BaseModel):
    """Represents a unique semantic symbolic state in the reachable graph."""
    node_id: str
    id: Optional[str] = None
    facts: List[str]
    depth: int = 0
    is_initial: bool = False
    is_goal: bool = False
    is_dead_end: bool = False
    is_boundary: bool = False
    is_truncated_boundary: Optional[bool] = None
    expanded: bool = False
    partially_expanded: bool = False
    summary: str = ""
    g_cost: Optional[float] = None
    h_cost: Optional[float] = None
    f_cost: Optional[float] = None

    def model_post_init(self, __context: Any) -> None:
        if self.id is None:
            self.id = self.node_id
        if self.is_truncated_boundary is None:
            self.is_truncated_boundary = self.is_boundary or self.partially_expanded


class GraphEdge(BaseModel):
    """Represents an authoritative directed transition between two symbolic states."""
    edge_id: str
    id: Optional[str] = None
    source_id: str
    source: Optional[str] = None
    target_id: str
    target: Optional[str] = None
    action_name: str
    action_args: List[str]
    action_label: str
    label: Optional[str] = None
    cost: float = 1.0
    is_plan_edge: bool = False
    is_repaired_edge: bool = False

    def model_post_init(self, __context: Any) -> None:
        if self.id is None:
            self.id = self.edge_id
        if self.source is None:
            self.source = self.source_id
        if self.target is None:
            self.target = self.target_id
        if self.label is None:
            self.label = self.action_label


class GraphStats(BaseModel):
    """Summary statistics for the enumerated state-space graph."""
    total_nodes: int = 0
    total_edges: int = 0
    initial_node_id: str = ""
    goal_node_ids: List[str] = Field(default_factory=list)
    dead_end_node_ids: List[str] = Field(default_factory=list)
    max_depth: int = 0
    max_depth_reached: Optional[int] = None
    is_complete: bool = False
    truncation_reason: Optional[str] = None
    enumeration_time_ms: float = 0.0
    duplicate_states_pruned: int = 0
    cycles_detected: int = 0

    def model_post_init(self, __context: Any) -> None:
        if self.max_depth_reached is None:
            self.max_depth_reached = self.max_depth


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
                    "node_id": n.node_id,
                    "label": f"S{n.depth}: {n.summary[:24]}" if n.summary else n.node_id[:8],
                    "depth": n.depth,
                    "is_initial": n.is_initial,
                    "is_goal": n.is_goal,
                    "is_dead_end": n.is_dead_end,
                    "is_boundary": n.is_boundary or n.partially_expanded,
                    "is_truncated_boundary": n.is_boundary or n.partially_expanded,
                    "partially_expanded": n.partially_expanded,
                    "expanded": n.expanded,
                    "facts": n.facts,
                    "facts_summary": n.facts[:6],
                },
                "classes": " ".join(classes),
            })

        # Edges
        for e in self.edges:
            cy_elements.append({
                "data": {
                    "id": e.edge_id,
                    "edge_id": e.edge_id,
                    "source": e.source_id,
                    "source_id": e.source_id,
                    "target": e.target_id,
                    "target_id": e.target_id,
                    "action_name": e.action_name,
                    "action_args": e.action_args,
                    "action_label": e.action_label,
                    "label": e.action_label,
                    "cost": e.cost,
                    "is_plan_edge": e.is_plan_edge,
                    "is_repaired_edge": e.is_repaired_edge,
                },
                "classes": "plan_edge" if e.is_plan_edge else "regular_edge",
            })

        stats_data = self.stats.model_dump()
        stats_data["max_depth_reached"] = self.stats.max_depth
        stats_data["max_depth"] = self.stats.max_depth

        return {
            "format": "cytoscape",
            "graph_id": self.graph_id,
            "domain_id": self.domain_id,
            "problem_name": self.problem_name,
            "stats": stats_data,
            "elements": cy_elements,
        }
