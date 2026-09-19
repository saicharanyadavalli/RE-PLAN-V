"""Classical search planners: BFS, Greedy Best-First, and A*."""

from __future__ import annotations

import collections
import heapq
import time
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, FrozenSet, List, Optional, Sequence, Set, Tuple

from core.actions.domain import Domain
from core.actions.generator import LegalActionGenerator
from core.actions.instantiation import GroundAction
from core.actions.transition import apply_transition
from core.contracts import GroundActionSchema, PlanSchema
from core.search.heuristics import GoalCountHeuristic, Heuristic, ZeroHeuristic
from core.search.node import SearchNode
from core.world.predicates import Fact
from core.world.problem import SymbolicProblem
from core.world.state import SymbolicState


class BasePlanner(ABC):
    """Abstract base class for state-space search planners."""

    def __init__(
        self,
        name: str,
        max_nodes_expanded: int = 10000,
        timeout_seconds: float = 10.0,
    ) -> None:
        self.name = name
        self.max_nodes_expanded = max_nodes_expanded
        self.timeout_seconds = timeout_seconds

    @abstractmethod
    def search(
        self,
        problem: SymbolicProblem,
        domain: Domain,
        heuristic: Optional[Heuristic] = None,
        forbidden_actions: Optional[Set[GroundAction]] = None,
        prune_action_callback: Optional[Callable[[SymbolicState, GroundAction], bool]] = None,
    ) -> PlanSchema:
        pass


class BFSPlanner(BasePlanner):
    """Breadth-First Search planner (FIFO queue, optimal for unit action costs)."""

    def __init__(self, max_nodes_expanded: int = 10000, timeout_seconds: float = 10.0) -> None:
        super().__init__("BFS", max_nodes_expanded, timeout_seconds)

    def search(
        self,
        problem: SymbolicProblem,
        domain: Domain,
        heuristic: Optional[Heuristic] = None,
        forbidden_actions: Optional[Set[GroundAction]] = None,
        prune_action_callback: Optional[Callable[[SymbolicState, GroundAction], bool]] = None,
    ) -> PlanSchema:
        start_time = time.perf_counter()
        forbidden = forbidden_actions or set()

        # Check if initial state satisfies goal
        if problem.is_goal_satisfied(problem.initial_state):
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return PlanSchema(
                actions=[],
                algorithm=self.name,
                total_cost=0.0,
                planning_time_ms=elapsed_ms,
                nodes_expanded=0,
                nodes_generated=1,
                is_success=True,
            )

        root = SearchNode(state=problem.initial_state)
        queue: collections.deque[SearchNode] = collections.deque([root])
        closed_set: Set[FrozenSet[Fact]] = {problem.initial_state.facts}

        action_gen = LegalActionGenerator(domain.get_all_actions(), problem.registry)
        nodes_expanded = 0
        nodes_generated = 1

        while queue:
            if nodes_expanded >= self.max_nodes_expanded:
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                return PlanSchema(
                    actions=[],
                    algorithm=self.name,
                    planning_time_ms=elapsed_ms,
                    nodes_expanded=nodes_expanded,
                    nodes_generated=nodes_generated,
                    is_success=False,
                    failure_reason="Search limit exceeded: max nodes expanded reached",
                )

            if (time.perf_counter() - start_time) > self.timeout_seconds:
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                return PlanSchema(
                    actions=[],
                    algorithm=self.name,
                    planning_time_ms=elapsed_ms,
                    nodes_expanded=nodes_expanded,
                    nodes_generated=nodes_generated,
                    is_success=False,
                    failure_reason="Search timeout exceeded",
                )

            curr_node = queue.popleft()
            nodes_expanded += 1

            applicable = action_gen.get_applicable_actions(curr_node.state)
            for act in applicable:
                # 1. Check forbidden actions from repair
                if act in forbidden:
                    continue
                if prune_action_callback and prune_action_callback(curr_node.state, act):
                    continue

                # 2. Check hard constraints
                ok_hc, _ = problem.check_hard_constraints(curr_node.state, act.name, act.arguments)
                if not ok_hc:
                    continue

                # 3. Apply authoritative transition
                next_state, err = apply_transition(curr_node.state, act)
                if err is not None:
                    continue

                # 4. Check invariants
                ok_inv, _ = problem.check_invariants(next_state)
                if not ok_inv:
                    continue

                # 5. Check if goal is reached
                if problem.is_goal_satisfied(next_state):
                    child_node = SearchNode(
                        state=next_state,
                        parent=curr_node,
                        action=act,
                        g_cost=curr_node.g_cost + act.cost,
                    )
                    plan_acts = child_node.extract_plan()
                    elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                    return PlanSchema(
                        actions=[a.to_schema() for a in plan_acts],
                        algorithm=self.name,
                        total_cost=child_node.g_cost,
                        planning_time_ms=elapsed_ms,
                        nodes_expanded=nodes_expanded,
                        nodes_generated=nodes_generated + 1,
                        is_success=True,
                    )

                # 6. Cycle detection
                if next_state.facts not in closed_set:
                    closed_set.add(next_state.facts)
                    child_node = SearchNode(
                        state=next_state,
                        parent=curr_node,
                        action=act,
                        g_cost=curr_node.g_cost + act.cost,
                    )
                    queue.append(child_node)
                    nodes_generated += 1

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        return PlanSchema(
            actions=[],
            algorithm=self.name,
            planning_time_ms=elapsed_ms,
            nodes_expanded=nodes_expanded,
            nodes_generated=nodes_generated,
            is_success=False,
            failure_reason="Search exhausted: no valid plan exists in state space",
        )


class BestFirstPlanner(BasePlanner):
    """Greedy Best-First Search planner (PriorityQueue ordered strictly by h_cost)."""

    def __init__(self, max_nodes_expanded: int = 10000, timeout_seconds: float = 10.0) -> None:
        super().__init__("BEST_FIRST", max_nodes_expanded, timeout_seconds)

    def search(
        self,
        problem: SymbolicProblem,
        domain: Domain,
        heuristic: Optional[Heuristic] = None,
        forbidden_actions: Optional[Set[GroundAction]] = None,
        prune_action_callback: Optional[Callable[[SymbolicState, GroundAction], bool]] = None,
    ) -> PlanSchema:
        start_time = time.perf_counter()
        h_fn = heuristic or GoalCountHeuristic()
        forbidden = forbidden_actions or set()

        if problem.is_goal_satisfied(problem.initial_state):
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return PlanSchema(
                actions=[],
                algorithm=self.name,
                total_cost=0.0,
                planning_time_ms=elapsed_ms,
                nodes_expanded=0,
                nodes_generated=1,
                is_success=True,
            )

        root_h = h_fn.compute(problem.initial_state, problem.goal_conditions)
        root = SearchNode(state=problem.initial_state, h_cost=root_h)
        # Priority queue entry: (h_cost, depth, node_id, node)
        frontier: List[Tuple[float, int, int, SearchNode]] = [
            (root_h, root.depth, root.node_id, root)
        ]
        closed_set: Set[FrozenSet[Fact]] = set()

        action_gen = LegalActionGenerator(domain.get_all_actions(), problem.registry)
        nodes_expanded = 0
        nodes_generated = 1

        while frontier:
            if nodes_expanded >= self.max_nodes_expanded:
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                return PlanSchema(
                    actions=[],
                    algorithm=self.name,
                    planning_time_ms=elapsed_ms,
                    nodes_expanded=nodes_expanded,
                    nodes_generated=nodes_generated,
                    is_success=False,
                    failure_reason="Search limit exceeded: max nodes expanded reached",
                )

            if (time.perf_counter() - start_time) > self.timeout_seconds:
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                return PlanSchema(
                    actions=[],
                    algorithm=self.name,
                    planning_time_ms=elapsed_ms,
                    nodes_expanded=nodes_expanded,
                    nodes_generated=nodes_generated,
                    is_success=False,
                    failure_reason="Search timeout exceeded",
                )

            _, _, _, curr_node = heapq.heappop(frontier)

            if curr_node.state.facts in closed_set:
                continue
            closed_set.add(curr_node.state.facts)
            nodes_expanded += 1

            if problem.is_goal_satisfied(curr_node.state):
                plan_acts = curr_node.extract_plan()
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                return PlanSchema(
                    actions=[a.to_schema() for a in plan_acts],
                    algorithm=self.name,
                    total_cost=curr_node.g_cost,
                    planning_time_ms=elapsed_ms,
                    nodes_expanded=nodes_expanded,
                    nodes_generated=nodes_generated,
                    is_success=True,
                )

            applicable = action_gen.get_applicable_actions(curr_node.state)
            for act in applicable:
                if act in forbidden:
                    continue
                if prune_action_callback and prune_action_callback(curr_node.state, act):
                    continue

                ok_hc, _ = problem.check_hard_constraints(curr_node.state, act.name, act.arguments)
                if not ok_hc:
                    continue

                next_state, err = apply_transition(curr_node.state, act)
                if err is not None:
                    continue

                ok_inv, _ = problem.check_invariants(next_state)
                if not ok_inv:
                    continue

                if next_state.facts not in closed_set:
                    h_val = h_fn.compute(next_state, problem.goal_conditions)
                    child_node = SearchNode(
                        state=next_state,
                        parent=curr_node,
                        action=act,
                        g_cost=curr_node.g_cost + act.cost,
                        h_cost=h_val,
                    )
                    heapq.heappush(frontier, (h_val, child_node.depth, child_node.node_id, child_node))
                    nodes_generated += 1

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        return PlanSchema(
            actions=[],
            algorithm=self.name,
            planning_time_ms=elapsed_ms,
            nodes_expanded=nodes_expanded,
            nodes_generated=nodes_generated,
            is_success=False,
            failure_reason="Search exhausted: no valid plan exists in state space",
        )


class AStarPlanner(BasePlanner):
    """A* Search planner (PriorityQueue ordered by f_cost = g_cost + h_cost)."""

    def __init__(self, max_nodes_expanded: int = 10000, timeout_seconds: float = 10.0) -> None:
        super().__init__("A*", max_nodes_expanded, timeout_seconds)

    def search(
        self,
        problem: SymbolicProblem,
        domain: Domain,
        heuristic: Optional[Heuristic] = None,
        forbidden_actions: Optional[Set[GroundAction]] = None,
        prune_action_callback: Optional[Callable[[SymbolicState, GroundAction], bool]] = None,
    ) -> PlanSchema:
        start_time = time.perf_counter()
        h_fn = heuristic or GoalCountHeuristic()
        forbidden = forbidden_actions or set()

        if problem.is_goal_satisfied(problem.initial_state):
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return PlanSchema(
                actions=[],
                algorithm=self.name,
                total_cost=0.0,
                planning_time_ms=elapsed_ms,
                nodes_expanded=0,
                nodes_generated=1,
                is_success=True,
            )

        root_h = h_fn.compute(problem.initial_state, problem.goal_conditions)
        root = SearchNode(state=problem.initial_state, g_cost=0.0, h_cost=root_h)

        # frontier holds SearchNode directly using SearchNode.__lt__
        frontier: List[SearchNode] = [root]
        # best_g records minimum known g_cost for each state
        best_g: Dict[FrozenSet[Fact], float] = {problem.initial_state.facts: 0.0}

        action_gen = LegalActionGenerator(domain.get_all_actions(), problem.registry)
        nodes_expanded = 0
        nodes_generated = 1

        while frontier:
            if nodes_expanded >= self.max_nodes_expanded:
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                return PlanSchema(
                    actions=[],
                    algorithm=self.name,
                    planning_time_ms=elapsed_ms,
                    nodes_expanded=nodes_expanded,
                    nodes_generated=nodes_generated,
                    is_success=False,
                    failure_reason="Search limit exceeded: max nodes expanded reached",
                )

            if (time.perf_counter() - start_time) > self.timeout_seconds:
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                return PlanSchema(
                    actions=[],
                    algorithm=self.name,
                    planning_time_ms=elapsed_ms,
                    nodes_expanded=nodes_expanded,
                    nodes_generated=nodes_generated,
                    is_success=False,
                    failure_reason="Search timeout exceeded",
                )

            curr_node = heapq.heappop(frontier)

            # Skip if we already found a strictly cheaper path to this state
            if curr_node.g_cost > best_g.get(curr_node.state.facts, float("inf")):
                continue

            nodes_expanded += 1

            if problem.is_goal_satisfied(curr_node.state):
                plan_acts = curr_node.extract_plan()
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                return PlanSchema(
                    actions=[a.to_schema() for a in plan_acts],
                    algorithm=self.name,
                    total_cost=curr_node.g_cost,
                    planning_time_ms=elapsed_ms,
                    nodes_expanded=nodes_expanded,
                    nodes_generated=nodes_generated,
                    is_success=True,
                )

            applicable = action_gen.get_applicable_actions(curr_node.state)
            for act in applicable:
                if act in forbidden:
                    continue
                if prune_action_callback and prune_action_callback(curr_node.state, act):
                    continue

                ok_hc, _ = problem.check_hard_constraints(curr_node.state, act.name, act.arguments)
                if not ok_hc:
                    continue

                next_state, err = apply_transition(curr_node.state, act)
                if err is not None:
                    continue

                ok_inv, _ = problem.check_invariants(next_state)
                if not ok_inv:
                    continue

                new_g = curr_node.g_cost + act.cost
                if new_g < best_g.get(next_state.facts, float("inf")):
                    best_g[next_state.facts] = new_g
                    h_val = h_fn.compute(next_state, problem.goal_conditions)
                    child_node = SearchNode(
                        state=next_state,
                        parent=curr_node,
                        action=act,
                        g_cost=new_g,
                        h_cost=h_val,
                    )
                    heapq.heappush(frontier, child_node)
                    nodes_generated += 1

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        return PlanSchema(
            actions=[],
            algorithm=self.name,
            planning_time_ms=elapsed_ms,
            nodes_expanded=nodes_expanded,
            nodes_generated=nodes_generated,
            is_success=False,
            failure_reason="Search exhausted: no valid plan exists in state space",
        )


def get_planner_by_name(name: str) -> BasePlanner:
    n = name.strip().upper()
    if n == "BFS":
        return BFSPlanner()
    elif n in ("BEST_FIRST", "BESTFIRST", "GREEDY"):
        return BestFirstPlanner()
    elif n in ("A*", "ASTAR"):
        return AStarPlanner()
    raise ValueError(f"Unknown planner algorithm '{name}'. Choose from 'BFS', 'BEST_FIRST', 'A*'.")
