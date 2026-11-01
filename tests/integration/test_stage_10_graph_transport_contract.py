"""Integration tests for Stage 10 DEF-10.5, 10.6, 10.7: Graph DTO and Frontend transport contract."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from core.actions.domain import create_blocks_world_domain
from core.graph.enumerator import CompleteReachableGraphEnumerator
from core.graph.models import GraphEdge, GraphNode, GraphStats, ReachableStateGraph
from core.world.predicates import Fact
from core.world.problem import SymbolicProblem
from core.world.state import SymbolicState
from core.world.types import ObjectRegistry


@pytest.fixture
def client():
    return TestClient(create_app())


def test_graph_node_and_edge_bidirectional_fields():
    node = GraphNode(
        node_id="s_init_123",
        facts=["on_table(a)", "clear(a)"],
        depth=0,
        is_initial=True,
        is_boundary=False,
    )
    # Both node_id and id must be populated
    assert node.node_id == "s_init_123"
    assert node.id == "s_init_123"
    assert node.is_boundary is False
    assert node.is_truncated_boundary is False

    edge = GraphEdge(
        edge_id="e_0_1",
        source_id="s_init_123",
        target_id="s_next_456",
        action_name="pick_up",
        action_args=["a"],
        action_label="pick_up(a)",
        cost=1.0,
    )
    # Both source_id / source and target_id / target must be populated
    assert edge.edge_id == "e_0_1"
    assert edge.id == "e_0_1"
    assert edge.source_id == "s_init_123"
    assert edge.source == "s_init_123"
    assert edge.target_id == "s_next_456"
    assert edge.target == "s_next_456"
    assert edge.action_label == "pick_up(a)"
    assert edge.label == "pick_up(a)"

    stats = GraphStats(total_nodes=5, total_edges=8, max_depth=3)
    assert stats.max_depth == 3
    assert stats.max_depth_reached == 3


def test_to_cytoscape_contract_contains_dual_fields():
    domain = create_blocks_world_domain()
    reg = ObjectRegistry(domain.type_hierarchy)
    reg.register_object("a", "block")
    reg.register_object("b", "block")
    s0 = SymbolicState([
        Fact("on_table", ["a"]),
        Fact("clear", ["a"]),
        Fact("on_table", ["b"]),
        Fact("clear", ["b"]),
        Fact("handempty", []),
    ])
    goals = [Fact("on", ["a", "b"])]
    problem = SymbolicProblem("simple", "blocks_world", reg, s0, goals)

    enumerator = CompleteReachableGraphEnumerator(max_nodes=10, max_edges=20)
    graph = enumerator.enumerate_graph(problem, domain)
    cy = graph.to_cytoscape()

    assert "elements" in cy
    assert "stats" in cy
    # Stats dual depth fields
    assert "max_depth" in cy["stats"]
    assert "max_depth_reached" in cy["stats"]

    # Verify node elements
    node_elements = [el for el in cy["elements"] if "source" not in el["data"]]
    assert len(node_elements) > 0
    for ne in node_elements:
        d = ne["data"]
        assert "id" in d
        assert "node_id" in d
        assert d["id"] == d["node_id"]
        assert "is_boundary" in d
        assert "is_truncated_boundary" in d
        assert "facts" in d
        assert "facts_summary" in d

    # Verify edge elements
    edge_elements = [el for el in cy["elements"] if "source" in el["data"]]
    assert len(edge_elements) > 0
    for ee in edge_elements:
        d = ee["data"]
        assert "id" in d
        assert "edge_id" in d
        assert "source" in d
        assert "source_id" in d
        assert "target" in d
        assert "target_id" in d
        assert "action_label" in d
        assert "label" in d


def test_api_benchmark_attribution_endpoint(client: TestClient):
    # Both /api/benchmark/attribution and /api/benchmark/attribution_matrix must return 200
    r1 = client.get("/api/benchmark/attribution")
    assert r1.status_code == 200
    data1 = r1.json()
    assert "confusion_matrix" in data1
    assert "accuracy" in data1
    assert "macro_f1" in data1
    assert data1["total_evaluated"] >= 50

    r2 = client.get("/api/benchmark/attribution_matrix")
    assert r2.status_code == 200
    assert r2.json()["total_evaluated"] == data1["total_evaluated"]
