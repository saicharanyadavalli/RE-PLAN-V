"""Stage 11 Integration Tests: Parity between REST /api/graph/enumerate and WebSocket /ws/pipeline."""

from __future__ import annotations

import json
import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client():
    return TestClient(create_app())


def test_rest_and_websocket_graph_parity(client: TestClient):
    """Verify that REST and WebSocket graph enumerations yield identical graph structure and stats."""
    prompt = "Stack the red box on the blue box."
    domain_id = "blocks_world"
    max_nodes = 50
    max_edges = 150
    timeout_seconds = 3.0

    # 1. Query REST endpoint
    rest_resp = client.post(
        "/api/graph/enumerate",
        json={
            "domain_id": domain_id,
            "prompt": prompt,
            "max_nodes": max_nodes,
            "max_edges": max_edges,
            "timeout_seconds": timeout_seconds,
        },
    )
    assert rest_resp.status_code == 200
    rest_data = rest_resp.json()
    assert "elements" in rest_data
    assert "stats" in rest_data
    rest_stats = rest_data["stats"]

    rest_nodes = [el["data"] for el in rest_data["elements"] if "source" not in el["data"]]
    rest_edges = [el["data"] for el in rest_data["elements"] if "source" in el["data"]]

    # 2. Query WebSocket endpoint
    ws_events = []
    ws_nodes = []
    ws_edges = []
    ws_stats = None

    with client.websocket_connect("/ws/pipeline") as ws:
        ws.send_json({
            "domain_id": domain_id,
            "prompt": prompt,
            "max_nodes": max_nodes,
            "max_edges": max_edges,
            "graph_timeout": timeout_seconds,
            "enumerate_graph": True,
            "step_delay": 0.0,
        })

        while True:
            try:
                msg = ws.receive_json()
                ws_events.append(msg)
                stage = msg.get("stage")

                if stage == "GRAPH_NODE_BATCH":
                    ws_nodes.extend(msg["data"]["nodes"])
                elif stage == "GRAPH_EDGE_BATCH":
                    ws_edges.extend(msg["data"]["edges"])
                elif stage in ("GRAPH_ENUMERATION_COMPLETED", "GRAPH_ENUMERATION_TRUNCATED"):
                    ws_stats = msg["data"]["stats"]
                    break
                elif stage in ("PIPELINE_FINISHED", "ERROR", "PLANNING_FAILED"):
                    break
            except Exception:
                break

    assert ws_stats is not None, "WebSocket did not complete graph enumeration"

    # Compare node and edge counts
    assert len(rest_nodes) == len(ws_nodes), f"Node count mismatch: REST={len(rest_nodes)}, WS={len(ws_nodes)}"
    assert len(rest_edges) == len(ws_edges), f"Edge count mismatch: REST={len(rest_edges)}, WS={len(ws_edges)}"

    # Compare stats
    assert rest_stats["total_nodes"] == ws_stats["total_nodes"]
    assert rest_stats["total_edges"] == ws_stats["total_edges"]
    assert rest_stats["is_complete"] == ws_stats["is_complete"]
    assert rest_stats["max_depth"] == ws_stats["max_depth"]
    assert sorted(rest_stats["goal_node_ids"]) == sorted(ws_stats["goal_node_ids"])
    assert sorted(rest_stats["dead_end_node_ids"]) == sorted(ws_stats["dead_end_node_ids"])

    # Verify identical node IDs
    rest_node_ids = {n["id"] for n in rest_nodes}
    ws_node_ids = {n["node_id"] for n in ws_nodes}
    assert rest_node_ids == ws_node_ids
