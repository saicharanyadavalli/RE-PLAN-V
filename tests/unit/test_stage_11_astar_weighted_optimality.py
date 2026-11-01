"""Stage 11 Unit Tests: Independent A* Weighted-Cost Optimality Oracle and Cost Validation."""

from __future__ import annotations

import math
import pytest
from core.actions.definition import ActionDefinition, ActionParameter
from core.actions.domain import Domain
from core.actions.instantiation import GroundAction
from core.search.algorithms import AStarPlanner, BFSPlanner
from core.search.heuristics import ZeroHeuristic
from core.world.predicates import Fact, PredicateDefinition
from core.world.problem import SymbolicProblem
from core.world.state import SymbolicState
from core.world.types import ObjectRegistry, TypeHierarchy


def build_weighted_branching_domain_and_problem():
    """Builds a deterministic test domain with two alternative paths:
    
    Path A (Short but Expensive):
      start -> mid_exp (cost 10) -> goal (cost 10)  [2 steps, total cost 20]

    Path B (Longer but Cheap):
      start -> n1 (cost 1) -> n2 (cost 1) -> n3 (cost 1) -> goal (cost 1) [4 steps, total cost 4]
    """
    types = TypeHierarchy()
    types.add_type("node")

    pred_at = PredicateDefinition("at", ["node"])

    # Expensive actions (cost 10 each)
    act_exp1 = ActionDefinition(
        name="hop_exp1",
        parameters=[ActionParameter("from", "node"), ActionParameter("to", "node")],
        preconditions=[Fact("at", ["start"])],
        add_effects=[Fact("at", ["mid_exp"])],
        del_effects=[Fact("at", ["start"])],
        cost=10.0,
    )
    act_exp2 = ActionDefinition(
        name="hop_exp2",
        parameters=[ActionParameter("from", "node"), ActionParameter("to", "node")],
        preconditions=[Fact("at", ["mid_exp"])],
        add_effects=[Fact("at", ["goal"])],
        del_effects=[Fact("at", ["mid_exp"])],
        cost=10.0,
    )

    # Cheap actions (cost 1 each)
    act_ch1 = ActionDefinition(
        name="hop_ch1",
        parameters=[ActionParameter("from", "node"), ActionParameter("to", "node")],
        preconditions=[Fact("at", ["start"])],
        add_effects=[Fact("at", ["n1"])],
        del_effects=[Fact("at", ["start"])],
        cost=1.0,
    )
    act_ch2 = ActionDefinition(
        name="hop_ch2",
        parameters=[ActionParameter("from", "node"), ActionParameter("to", "node")],
        preconditions=[Fact("at", ["n1"])],
        add_effects=[Fact("at", ["n2"])],
        del_effects=[Fact("at", ["n1"])],
        cost=1.0,
    )
    act_ch3 = ActionDefinition(
        name="hop_ch3",
        parameters=[ActionParameter("from", "node"), ActionParameter("to", "node")],
        preconditions=[Fact("at", ["n2"])],
        add_effects=[Fact("at", ["n3"])],
        del_effects=[Fact("at", ["n2"])],
        cost=1.0,
    )
    act_ch4 = ActionDefinition(
        name="hop_ch4",
        parameters=[ActionParameter("from", "node"), ActionParameter("to", "node")],
        preconditions=[Fact("at", ["n3"])],
        add_effects=[Fact("at", ["goal"])],
        del_effects=[Fact("at", ["n3"])],
        cost=1.0,
    )

    domain = Domain(
        name="weighted_graph",
        actions=[act_exp1, act_exp2, act_ch1, act_ch2, act_ch3, act_ch4],
        predicates=[pred_at],
        type_hierarchy=types,
    )

    reg = ObjectRegistry(types)
    for n in ["start", "mid_exp", "n1", "n2", "n3", "goal"]:
        reg.register_object(n, "node")

    s0 = SymbolicState([Fact("at", ["start"])], objects=reg.get_all_objects())
    goals = [Fact("at", ["goal"])]
    problem = SymbolicProblem("test_weighted", "weighted_graph", reg, s0, goals)

    return domain, problem


def test_astar_finds_minimum_cost_path_unlike_bfs():
    """Verify that A* (UCS) strictly minimizes cumulative edge cost rather than step count."""
    domain, problem = build_weighted_branching_domain_and_problem()

    # 1. BFS prioritizes step count (finds 2-step path of cost 20)
    bfs = BFSPlanner()
    bfs_plan = bfs.search(problem, domain)
    assert bfs_plan.is_success is True
    assert len(bfs_plan.actions) == 2
    assert bfs_plan.total_cost == 20.0

    # 2. A* with ZeroHeuristic strictly finds the 4-step path of cost 4
    astar = AStarPlanner()
    astar_plan = astar.search(problem, domain, heuristic=ZeroHeuristic())
    assert astar_plan.is_success is True
    assert len(astar_plan.actions) == 4
    assert astar_plan.total_cost == 4.0
    assert astar_plan.is_optimal is True

    action_names = [a.name for a in astar_plan.actions]
    assert action_names == ["hop_ch1", "hop_ch2", "hop_ch3", "hop_ch4"]


def test_astar_rejects_negative_action_cost():
    """Verify that A* strictly raises ValueError when encountering negative action costs."""
    types = TypeHierarchy()
    types.add_type("node")
    pred_at = PredicateDefinition("at", ["node"])

    bad_act = ActionDefinition(
        name="negative_act",
        parameters=[ActionParameter("n", "node")],
        preconditions=[Fact("at", ["start"])],
        add_effects=[Fact("at", ["goal"])],
        del_effects=[],
        cost=-5.0,  # Negative cost violates non-negative edge weight assumption
    )
    domain = Domain(name="neg_domain", actions=[bad_act], predicates=[pred_at], type_hierarchy=types)

    reg = ObjectRegistry(types)
    reg.register_object("start", "node")
    reg.register_object("goal", "node")

    s0 = SymbolicState([Fact("at", ["start"])], objects=reg.get_all_objects())
    goals = [Fact("at", ["goal"])]
    problem = SymbolicProblem("neg_test", "neg_domain", reg, s0, goals)

    astar = AStarPlanner()
    with pytest.raises(ValueError, match="invalid negative or non-finite cost"):
        astar.search(problem, domain)
