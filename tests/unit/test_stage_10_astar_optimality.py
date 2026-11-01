"""Unit tests for Stage 10 DEF-10.4: A* Heuristic Admissibility and Plan Optimality."""

from __future__ import annotations

import pytest
from core.actions.domain import create_blocks_world_domain
from core.actions.instantiation import GroundAction
from core.contracts import FactSchema, TaskProposalSchema
from core.search.algorithms import AStarPlanner, BFSPlanner, BestFirstPlanner
from core.search.heuristics import GoalCountHeuristic, ZeroHeuristic
from core.world.predicates import Fact
from core.world.problem import SymbolicProblem
from core.world.state import SymbolicState
from core.world.types import ObjectRegistry, TypeHierarchy


def test_astar_default_heuristic_is_zero_heuristic_and_guarantees_optimality():
    domain = create_blocks_world_domain()
    reg = ObjectRegistry(domain.type_hierarchy)
    for b in ["a", "b", "c"]:
        reg.register_object(b, "block")

    # Initial: a on table, b on table, c on table
    s0 = SymbolicState([
        Fact("on_table", ["a"]),
        Fact("clear", ["a"]),
        Fact("on_table", ["b"]),
        Fact("clear", ["b"]),
        Fact("on_table", ["c"]),
        Fact("clear", ["c"]),
        Fact("handempty", []),
    ])
    # Goal: a on b, b on c (tower of 3 blocks)
    goals = [
        Fact("on", ["a", "b"]),
        Fact("on", ["b", "c"]),
    ]
    problem = SymbolicProblem(
        name="tower_3_optimality",
        domain_name="blocks_world",
        registry=reg,
        initial_state=s0,
        goal_conditions=goals,
    )

    astar = AStarPlanner()
    plan = astar.search(problem, domain)

    assert plan.is_success is True
    # Default A* plan must be marked optimal
    assert plan.is_optimal is True
    # In blocks world, building a on b and b on c from table takes:
    # 1. pick_up(b), 2. stack(b, c), 3. pick_up(a), 4. stack(a, b) -> 4 steps
    assert len(plan.actions) == 4
    assert plan.total_cost == 4.0


def test_bfs_marked_optimal():
    domain = create_blocks_world_domain()
    reg = ObjectRegistry(domain.type_hierarchy)
    for b in ["a", "b"]:
        reg.register_object(b, "block")

    s0 = SymbolicState([
        Fact("on_table", ["a"]),
        Fact("clear", ["a"]),
        Fact("on_table", ["b"]),
        Fact("clear", ["b"]),
        Fact("handempty", []),
    ])
    goals = [Fact("on", ["a", "b"])]
    problem = SymbolicProblem("simple_stack", "blocks_world", reg, s0, goals)

    bfs = BFSPlanner()
    plan = bfs.search(problem, domain)
    assert plan.is_success is True
    assert plan.is_optimal is True
    assert len(plan.actions) == 2


def test_greedy_best_first_not_marked_optimal():
    domain = create_blocks_world_domain()
    reg = ObjectRegistry(domain.type_hierarchy)
    for b in ["a", "b"]:
        reg.register_object(b, "block")

    s0 = SymbolicState([
        Fact("on_table", ["a"]),
        Fact("clear", ["a"]),
        Fact("on_table", ["b"]),
        Fact("clear", ["b"]),
        Fact("handempty", []),
    ])
    goals = [Fact("on", ["a", "b"])]
    problem = SymbolicProblem("simple_stack", "blocks_world", reg, s0, goals)

    greedy = BestFirstPlanner()
    plan = greedy.search(problem, domain)
    assert plan.is_success is True
    # Greedy best-first does NOT guarantee cost optimality
    assert plan.is_optimal is False
