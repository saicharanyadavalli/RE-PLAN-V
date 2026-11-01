"""Model B: Complete Reachable-State Graph Enumerator.

Enumerate all reachable unique symbolic states and valid directed transitions
from an initial state, enforcing exact semantic deduplication, cycle detection,
and strict resource budgets.
"""

from __future__ import annotations

import collections
import time
import uuid
from typing import Dict, List, Optional, Set, Tuple

from core.domains.base import BaseDomain
from core.graph.models import GraphEdge, GraphNode, GraphStats, ReachableStateGraph
from core.world.problem import SymbolicProblem
from core.world.state import SymbolicState


class CompleteReachableGraphEnumerator:
    """Computes the full reachable state space for a given problem and domain."""

    def __init__(
        self,
        max_nodes: int = 500,
        max_edges: int = 1500,
        timeout_seconds: float = 5.0,
    ) -> None:
        self.max_nodes = max_nodes
        self.max_edges = max_edges
        self.timeout_seconds = timeout_seconds

    def enumerate_graph(
        self, problem: SymbolicProblem, domain: BaseDomain
    ) -> ReachableStateGraph:
        """Performs exhaustive reachable state-space exploration under strict budgets."""
        start_time = time.perf_counter()
        graph_id = f"graph_{uuid.uuid4().hex[:12]}"

        init_state = problem.initial_state
        init_id = domain.canonical_state_key(init_state)

        nodes: Dict[str, GraphNode] = {}
        edges: List[GraphEdge] = []
        seen_edges: Set[str] = set()
        seen_states: Dict[str, SymbolicState] = {init_id: init_state}

        is_goal_init = problem.is_goal_satisfied(init_state)
        nodes[init_id] = GraphNode(
            node_id=init_id,
            facts=sorted([f.to_string() for f in init_state.facts]),
            depth=0,
            is_initial=True,
            is_goal=is_goal_init,
            summary=domain.render_state_summary(init_state),
        )

        worklist = collections.deque([(init_state, 0)])
        is_complete = True
        truncation_reason: Optional[str] = None
        cycles_detected = 0
        duplicate_states_pruned = 0
        max_depth = 0

        while worklist:
            # Check timeout
            elapsed = time.perf_counter() - start_time
            if elapsed >= self.timeout_seconds:
                is_complete = False
                truncation_reason = "TIMEOUT"
                break

            curr_state, depth = worklist.popleft()
            curr_id = domain.canonical_state_key(curr_state)
            if depth > max_depth:
                max_depth = depth

            applicable = sorted(
                domain.applicable_actions(curr_state, problem.registry),
                key=lambda a: a.to_string(),
            )
            if not applicable and not nodes[curr_id].is_goal:
                nodes[curr_id].is_dead_end = True

            curr_fully_expanded = True
            for action in applicable:
                # Check timeout inside action expansion
                if (time.perf_counter() - start_time) >= self.timeout_seconds:
                    is_complete = False
                    truncation_reason = "TIMEOUT"
                    curr_fully_expanded = False
                    break

                # Check edge limit before generating transitions
                if len(edges) >= self.max_edges:
                    is_complete = False
                    truncation_reason = "MAX_EDGES_EXCEEDED"
                    curr_fully_expanded = False
                    break

                # Check problem-level hard constraints
                ok_hc, _ = problem.check_hard_constraints(
                    curr_state, action.name, list(action.arguments)
                )
                if not ok_hc:
                    continue

                # Apply STRIPS transition
                next_state, err = domain.apply_action(curr_state, action)
                if err is not None:
                    continue

                # Check invariants
                ok_d, _ = domain.check_invariants(next_state)
                if not ok_d:
                    continue
                ok_p, _ = problem.check_invariants(next_state)
                if not ok_p:
                    continue

                next_id = domain.canonical_state_key(next_state)

                if next_id in seen_states:
                    cycles_detected += 1
                    duplicate_states_pruned += 1
                else:
                    # Check node limit BEFORE creating target node and edge to guarantee endpoint exists
                    if len(nodes) >= self.max_nodes:
                        is_complete = False
                        truncation_reason = "MAX_NODES_EXCEEDED"
                        curr_fully_expanded = False
                        break

                    seen_states[next_id] = next_state
                    is_goal = problem.is_goal_satisfied(next_state)
                    nodes[next_id] = GraphNode(
                        node_id=next_id,
                        facts=sorted([f.to_string() for f in next_state.facts]),
                        depth=depth + 1,
                        is_goal=is_goal,
                        summary=domain.render_state_summary(next_state),
                    )
                    worklist.append((next_state, depth + 1))

                edge_sig = f"{curr_id}::{action.to_string()}::{next_id}"
                if edge_sig not in seen_edges:
                    seen_edges.add(edge_sig)
                    edges.append(
                        GraphEdge(
                            edge_id=f"e_{len(edges) + 1}",
                            source_id=curr_id,
                            target_id=next_id,
                            action_name=action.name,
                            action_args=list(action.arguments),
                            action_label=action.to_string(),
                            cost=action.cost,
                        )
                    )

            if curr_fully_expanded:
                nodes[curr_id].expanded = True
            else:
                nodes[curr_id].partially_expanded = True
                nodes[curr_id].is_boundary = True
                break

        # If truncated or frontier remaining, mark unexpanded/partially-expanded nodes as boundary
        if not is_complete or len(worklist) > 0:
            is_complete = False
            for n_id, n in nodes.items():
                if not n.expanded or n.partially_expanded:
                    n.is_boundary = True

        total_time_ms = (time.perf_counter() - start_time) * 1000.0
        goal_ids = [n.node_id for n in nodes.values() if n.is_goal]
        dead_ends = [n.node_id for n in nodes.values() if n.is_dead_end]

        stats = GraphStats(
            total_nodes=len(nodes),
            total_edges=len(edges),
            initial_node_id=init_id,
            goal_node_ids=goal_ids,
            dead_end_node_ids=dead_ends,
            max_depth=max_depth,
            is_complete=is_complete,
            truncation_reason=truncation_reason,
            enumeration_time_ms=total_time_ms,
            duplicate_states_pruned=duplicate_states_pruned,
            cycles_detected=cycles_detected,
        )

        return ReachableStateGraph(
            graph_id=graph_id,
            domain_id=domain.domain_id,
            problem_name=problem.name,
            nodes=nodes,
            edges=edges,
            stats=stats,
        )
