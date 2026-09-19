"""Unit tests for Stage 3: Classical Search Planners (BFS, Best-First, A*)."""

import pytest
from core.actions.domain import create_blocks_world_domain, create_gridworld_domain
from core.actions.generator import LegalActionGenerator
from core.actions.instantiation import GroundAction
from core.search.algorithms import AStarPlanner, BFSPlanner, BestFirstPlanner, get_planner_by_name
from core.search.heuristics import GoalCountHeuristic, RelaxedPlanningGraphHeuristic, ZeroHeuristic
from core.search.node import SearchNode
from core.world.constraints import ProhibitedEntityActionConstraint
from core.world.predicates import Fact
from core.world.problem import SymbolicProblem
from core.world.state import SymbolicState
from core.world.types import ObjectRegistry


def test_search_node_and_plan_extraction():
    s0 = SymbolicState(facts=[], objects={})
    n0 = SearchNode(state=s0)
    act1 = GroundAction("act1", ["x"], [], [], [])
    n1 = SearchNode(state=s0, parent=n0, action=act1, g_cost=1.0, h_cost=2.0)
    act2 = GroundAction("act2", ["y"], [], [], [])
    n2 = SearchNode(state=s0, parent=n1, action=act2, g_cost=2.0, h_cost=1.0)

    assert n2.depth == 2
    assert n2.f_cost == 3.0
    plan = n2.extract_plan()
    assert len(plan) == 2
    assert plan[0] == act1
    assert plan[1] == act2


def test_heuristics():
    domain = create_blocks_world_domain()
    reg = ObjectRegistry(domain.type_hierarchy)
    reg.register_object("b1", "block")
    reg.register_object("b2", "block")

    goals = [Fact("on", ["b1", "b2"]), Fact("clear", ["b1"])]
    s = SymbolicState(facts=[Fact("clear", ["b1"])], objects=reg.get_all_objects())

    # Zero Heuristic
    h0 = ZeroHeuristic()
    assert h0.compute(s, goals) == 0.0

    # Goal Count Heuristic: 1 of 2 goals is missing
    h_gc = GoalCountHeuristic()
    assert h_gc.compute(s, goals) == 1.0

    # Relaxed Planning Graph Heuristic
    gen = LegalActionGenerator(domain.get_all_actions(), reg)
    all_ground = gen.generate_all_ground_actions()
    h_rpg = RelaxedPlanningGraphHeuristic(all_ground, mode="h_max")
    val = h_rpg.compute(s, goals)
    assert val > 0.0


def test_bfs_two_blocks_stack():
    domain = create_blocks_world_domain()
    reg = ObjectRegistry(domain.type_hierarchy)
    reg.register_object("b1", "block")
    reg.register_object("b2", "block")

    init_state = SymbolicState(
        facts=[
            Fact("on_table", ["b1"]),
            Fact("clear", ["b1"]),
            Fact("on_table", ["b2"]),
            Fact("clear", ["b2"]),
            Fact("handempty", []),
        ],
        objects=reg.get_all_objects(),
    )

    problem = SymbolicProblem(
        name="two_block_stack",
        domain_name="blocks_world",
        registry=reg,
        initial_state=init_state,
        goal_conditions=[Fact("on", ["b1", "b2"])],
    )

    planner = BFSPlanner()
    plan = planner.search(problem, domain)

    assert plan.is_success
    assert len(plan.actions) == 2
    assert plan.actions[0].to_string() == "pick_up(b1)"
    assert plan.actions[1].to_string() == "stack(b1, b2)"
    assert plan.total_cost == 2.0


def test_astar_sussman_anomaly():
    """Classic Sussman Anomaly:
    Initial: C on A, A on table, B on table.
    Goal: A on B, B on C.
    """
    domain = create_blocks_world_domain()
    reg = ObjectRegistry(domain.type_hierarchy)
    reg.register_object("A", "block")
    reg.register_object("B", "block")
    reg.register_object("C", "block")

    init_state = SymbolicState(
        facts=[
            Fact("on", ["C", "A"]),
            Fact("clear", ["C"]),
            Fact("on_table", ["A"]),
            Fact("on_table", ["B"]),
            Fact("clear", ["B"]),
            Fact("handempty", []),
        ],
        objects=reg.get_all_objects(),
    )

    problem = SymbolicProblem(
        name="sussman_anomaly",
        domain_name="blocks_world",
        registry=reg,
        initial_state=init_state,
        goal_conditions=[Fact("on", ["A", "B"]), Fact("on", ["B", "C"])],
    )

    planner = AStarPlanner()
    plan = planner.search(problem, domain)

    assert plan.is_success
    # Optimal Sussman Anomaly plan length is 6 actions:
    # unstack(C,A), put_down(C), pick_up(B), stack(B,C), pick_up(A), stack(A,B)
    assert len(plan.actions) == 6
    act_names = [a.name for a in plan.actions]
    assert act_names == ["unstack", "put_down", "pick_up", "stack", "pick_up", "stack"]


def test_best_first_planner():
    domain = create_blocks_world_domain()
    reg = ObjectRegistry(domain.type_hierarchy)
    reg.register_object("b1", "block")
    reg.register_object("b2", "block")

    init_state = SymbolicState(
        facts=[
            Fact("on_table", ["b1"]),
            Fact("clear", ["b1"]),
            Fact("on_table", ["b2"]),
            Fact("clear", ["b2"]),
            Fact("handempty", []),
        ],
        objects=reg.get_all_objects(),
    )

    problem = SymbolicProblem(
        name="test_best_first",
        domain_name="blocks_world",
        registry=reg,
        initial_state=init_state,
        goal_conditions=[Fact("on", ["b1", "b2"])],
    )

    planner = BestFirstPlanner()
    plan = planner.search(problem, domain)
    assert plan.is_success
    assert len(plan.actions) == 2


def test_astar_gridworld_with_hard_constraint():
    domain = create_gridworld_domain()
    reg = ObjectRegistry(domain.type_hierarchy)
    reg.register_object("bot", "agent")
    reg.register_object("loc1", "location")
    reg.register_object("loc2", "location")
    reg.register_object("loc3", "location")
    reg.register_object("item1", "item")
    reg.register_object("fragile_vase", "item")

    init_state = SymbolicState(
        facts=[
            Fact("at", ["bot", "loc1"]),
            Fact("agent_free", ["bot"]),
            Fact("connected", ["loc1", "loc2"]),
            Fact("connected", ["loc2", "loc3"]),
            Fact("item_at", ["item1", "loc2"]),
            Fact("item_at", ["fragile_vase", "loc2"]),
        ],
        objects=reg.get_all_objects(),
    )

    # Goal: item1 at loc3. Also protect fragile_vase
    hc = ProhibitedEntityActionConstraint("fragile_vase", ["pick"])
    problem = SymbolicProblem(
        name="gridworld_task",
        domain_name="gridworld",
        registry=reg,
        initial_state=init_state,
        goal_conditions=[Fact("item_at", ["item1", "loc3"])],
        hard_constraints=[hc],
    )

    planner = AStarPlanner()
    plan = planner.search(problem, domain)

    assert plan.is_success
    # Plan: move(bot, loc1, loc2) -> pick(bot, item1, loc2) -> move(bot, loc2, loc3) -> drop(bot, item1, loc3)
    assert len(plan.actions) == 4
    for a in plan.actions:
        assert "fragile_vase" not in a.arguments


def test_unsolvable_problem_exhaustion():
    domain = create_blocks_world_domain()
    reg = ObjectRegistry(domain.type_hierarchy)
    reg.register_object("b1", "block")

    # Initial state with empty table, but goal is on(b1, b1) which can never be achieved
    init_state = SymbolicState(
        facts=[Fact("on_table", ["b1"]), Fact("clear", ["b1"]), Fact("handempty", [])],
        objects=reg.get_all_objects(),
    )

    problem = SymbolicProblem(
        name="unsolvable",
        domain_name="blocks_world",
        registry=reg,
        initial_state=init_state,
        goal_conditions=[Fact("on", ["b1", "b1"])],
    )

    planner = AStarPlanner(max_nodes_expanded=50)
    plan = planner.search(problem, domain)
    assert not plan.is_success
    assert "Search exhausted" in plan.failure_reason or "Search limit" in plan.failure_reason


def test_forbidden_action_search_pruning():
    """Tests that forbidden_actions passed to planner prevents choosing that action."""
    domain = create_blocks_world_domain()
    reg = ObjectRegistry(domain.type_hierarchy)
    reg.register_object("b1", "block")
    reg.register_object("b2", "block")

    init_state = SymbolicState(
        facts=[
            Fact("on_table", ["b1"]),
            Fact("clear", ["b1"]),
            Fact("on_table", ["b2"]),
            Fact("clear", ["b2"]),
            Fact("handempty", []),
        ],
        objects=reg.get_all_objects(),
    )

    problem = SymbolicProblem(
        name="test_forbid",
        domain_name="blocks_world",
        registry=reg,
        initial_state=init_state,
        goal_conditions=[Fact("on", ["b1", "b2"])],
    )

    # Forbid pick_up(b1)
    forbidden_act = domain.get_action("pick_up").instantiate({"?b": "b1"})
    planner = AStarPlanner()
    plan = planner.search(problem, domain, forbidden_actions={forbidden_act})

    # Since pick_up(b1) is forbidden and needed to stack b1 on b2, search should fail
    assert not plan.is_success
