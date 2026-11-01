"""Unit tests for the Complete State-Space Graph Explorer (Model B)."""

import pytest
from core.domains import registry
from core.graph.enumerator import CompleteReachableGraphEnumerator
from core.graph.models import ReachableStateGraph
from core.world.predicates import Fact
from core.world.problem import SymbolicProblem
from core.world.state import SymbolicState
from core.world.types import ObjectRegistry


def test_complete_reachable_graph_enumeration_2blocks():
    domain = registry.get("blocks_world")
    reg = ObjectRegistry(domain.type_hierarchy)
    reg.register_object("b1", "block")
    reg.register_object("b2", "block")

    # 2 blocks on table, hand empty
    s0 = SymbolicState([
        Fact("on_table", ["b1"]),
        Fact("on_table", ["b2"]),
        Fact("clear", ["b1"]),
        Fact("clear", ["b2"]),
        Fact("handempty", []),
    ])
    # Goal: b1 on b2
    goal = [Fact("on", ["b1", "b2"])]
    problem = SymbolicProblem(
        name="2blocks_test",
        domain_name="blocks_world",
        registry=reg,
        initial_state=s0,
        goal_conditions=goal,
    )

    enumerator = CompleteReachableGraphEnumerator(max_nodes=100, max_edges=200, timeout_seconds=5.0)
    graph = enumerator.enumerate_graph(problem, domain)

    assert isinstance(graph, ReachableStateGraph)
    assert graph.stats.is_complete is True
    assert graph.stats.truncation_reason is None
    assert graph.stats.total_nodes > 1
    assert graph.stats.total_edges > 1
    # Goal node must be identified
    assert len(graph.stats.goal_node_ids) >= 1
    goal_id = graph.stats.goal_node_ids[0]
    assert graph.nodes[goal_id].is_goal is True
    # Cycles must be detected since pick_up and put_down reverse each other
    assert graph.stats.cycles_detected > 0


def test_graph_truncation_when_max_nodes_exceeded():
    domain = registry.get("blocks_world")
    reg = ObjectRegistry(domain.type_hierarchy)
    for i in range(1, 5):
        reg.register_object(f"b{i}", "block")

    s0 = SymbolicState([
        Fact("on_table", [f"b{i}"]) for i in range(1, 5)
    ] + [
        Fact("clear", [f"b{i}"]) for i in range(1, 5)
    ] + [
        Fact("handempty", []),
    ])
    problem = SymbolicProblem(
        name="4blocks_truncate_test",
        domain_name="blocks_world",
        registry=reg,
        initial_state=s0,
        goal_conditions=[Fact("on", ["b1", "b2"])],
    )

    # Set very small node budget (e.g., 5 nodes)
    enumerator = CompleteReachableGraphEnumerator(max_nodes=5, timeout_seconds=5.0)
    graph = enumerator.enumerate_graph(problem, domain)

    assert graph.stats.is_complete is False
    assert graph.stats.truncation_reason == "MAX_NODES_EXCEEDED"
    assert graph.stats.total_nodes <= 6  # At budget boundary
    # Boundary nodes must be tagged
    boundary_nodes = [n for n in graph.nodes.values() if n.is_boundary]
    assert len(boundary_nodes) > 0


def test_graph_truncation_when_max_edges_exceeded():
    domain = registry.get("blocks_world")
    reg = ObjectRegistry(domain.type_hierarchy)
    for i in range(1, 4):
        reg.register_object(f"b{i}", "block")

    s0 = SymbolicState([
        Fact("on_table", [f"b{i}"]) for i in range(1, 4)
    ] + [
        Fact("clear", [f"b{i}"]) for i in range(1, 4)
    ] + [
        Fact("handempty", []),
    ])
    problem = SymbolicProblem(
        name="edge_truncate_test",
        domain_name="blocks_world",
        registry=reg,
        initial_state=s0,
        goal_conditions=[Fact("on", ["b1", "b2"])],
    )

    enumerator = CompleteReachableGraphEnumerator(max_nodes=100, max_edges=4, timeout_seconds=5.0)
    graph = enumerator.enumerate_graph(problem, domain)

    assert graph.stats.is_complete is False
    assert graph.stats.truncation_reason == "MAX_EDGES_EXCEEDED"
    assert graph.stats.total_edges <= 5


def test_all_edge_endpoints_exist_in_nodes():
    domain = registry.get("blocks_world")
    reg = ObjectRegistry(domain.type_hierarchy)
    for i in range(1, 4):
        reg.register_object(f"b{i}", "block")

    s0 = SymbolicState([
        Fact("on_table", [f"b{i}"]) for i in range(1, 4)
    ] + [
        Fact("clear", [f"b{i}"]) for i in range(1, 4)
    ] + [
        Fact("handempty", []),
    ])
    problem = SymbolicProblem(
        name="endpoints_test",
        domain_name="blocks_world",
        registry=reg,
        initial_state=s0,
        goal_conditions=[Fact("on", ["b1", "b2"])],
    )

    # Test under truncation
    for max_nodes in [2, 3, 5]:
        enumerator = CompleteReachableGraphEnumerator(max_nodes=max_nodes, max_edges=10, timeout_seconds=5.0)
        graph = enumerator.enumerate_graph(problem, domain)
        for edge in graph.edges:
            assert edge.source_id in graph.nodes, f"Edge {edge.edge_id} source {edge.source_id} not in nodes"
            assert edge.target_id in graph.nodes, f"Edge {edge.edge_id} target {edge.target_id} not in nodes"


def test_boundary_tagging_and_partial_expansion():
    domain = registry.get("blocks_world")
    reg = ObjectRegistry(domain.type_hierarchy)
    for i in range(1, 4):
        reg.register_object(f"b{i}", "block")

    s0 = SymbolicState([
        Fact("on_table", [f"b{i}"]) for i in range(1, 4)
    ] + [
        Fact("clear", [f"b{i}"]) for i in range(1, 4)
    ] + [
        Fact("handempty", []),
    ])
    problem = SymbolicProblem(
        name="boundary_tagging_test",
        domain_name="blocks_world",
        registry=reg,
        initial_state=s0,
        goal_conditions=[Fact("on", ["b1", "b2"])],
    )

    # Edge budget of 2 will interrupt expansion on the initial state (which has 3 pick_up actions)
    enumerator = CompleteReachableGraphEnumerator(max_nodes=50, max_edges=2, timeout_seconds=5.0)
    graph = enumerator.enumerate_graph(problem, domain)

    assert graph.stats.is_complete is False
    assert graph.stats.truncation_reason == "MAX_EDGES_EXCEEDED"
    init_node = graph.nodes[graph.stats.initial_node_id]
    assert init_node.partially_expanded is True
    assert init_node.is_boundary is True

    # Cytoscape export check
    cy = graph.to_cytoscape()
    init_cy = [el for el in cy["elements"] if el["data"]["id"] == init_node.node_id][0]
    assert "boundary" in init_cy["classes"]
    assert init_cy["data"]["partially_expanded"] is True


def test_graph_timeout_truncation():
    domain = registry.get("blocks_world")
    reg = ObjectRegistry(domain.type_hierarchy)
    for i in range(1, 5):
        reg.register_object(f"b{i}", "block")

    s0 = SymbolicState([
        Fact("on_table", [f"b{i}"]) for i in range(1, 5)
    ] + [
        Fact("clear", [f"b{i}"]) for i in range(1, 5)
    ] + [
        Fact("handempty", []),
    ])
    problem = SymbolicProblem(
        name="timeout_test",
        domain_name="blocks_world",
        registry=reg,
        initial_state=s0,
        goal_conditions=[Fact("on", ["b1", "b2"])],
    )

    # Very short timeout
    enumerator = CompleteReachableGraphEnumerator(max_nodes=1000, max_edges=3000, timeout_seconds=0.00001)
    graph = enumerator.enumerate_graph(problem, domain)

    assert graph.stats.is_complete is False
    assert graph.stats.truncation_reason == "TIMEOUT"
    boundary_nodes = [n for n in graph.nodes.values() if n.is_boundary]
    assert len(boundary_nodes) > 0
