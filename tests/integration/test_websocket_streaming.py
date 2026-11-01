"""Integration tests for FastAPI WebSocket streaming endpoint."""

import pytest
from fastapi.testclient import TestClient
from app.main import create_app


def test_websocket_pipeline_streaming_valid():
    app = create_app()
    client = TestClient(app)
    with client.websocket_connect("/ws/pipeline") as websocket:
        websocket.send_json({
            "prompt": "Move the red box next to the blue box. Do not move the glass.",
            "algorithm": "A*",
            "force_fault": False,
            "provider_type": "mock",
            "step_delay": 0.0,
        })

        stages_received = []
        while True:
            data = websocket.receive_json()
            stages_received.append(data["stage"])
            if data["stage"] in ("PIPELINE_FINISHED", "ERROR"):
                break

        assert "PIPELINE_STARTED" in stages_received
        assert "INTERPRETATION_COMPLETED" in stages_received
        assert "SEARCH_COMPLETED" in stages_received
        assert "FINAL_VERIFICATION" in stages_received
        assert "PIPELINE_FINISHED" in stages_received


def test_websocket_pipeline_streaming_with_fault_repair():
    app = create_app()
    client = TestClient(app)
    with client.websocket_connect("/ws/pipeline") as websocket:
        websocket.send_json({
            "prompt": "Move the red box next to the blue box. Do not move the glass.",
            "algorithm": "A*",
            "force_fault": True,
            "provider_type": "mock",
            "step_delay": 0.0,
        })

        stages_received = []
        while True:
            data = websocket.receive_json()
            stages_received.append(data["stage"])
            if data["stage"] in ("PIPELINE_FINISHED", "ERROR"):
                break

        assert "PIPELINE_STARTED" in stages_received
        assert "VERIFICATION_FAILED" in stages_received
        assert "COUNTEREXAMPLE_EXTRACTED" in stages_received
        assert "ATTRIBUTION_CLASSIFIED" in stages_received
        assert "REPAIR_INJECTED" in stages_received
        assert "FINAL_VERIFICATION" in stages_received
        assert "PIPELINE_FINISHED" in stages_received


def test_websocket_streaming_with_graph_enumeration_batching():
    app = create_app()
    client = TestClient(app)
    with client.websocket_connect("/ws/pipeline") as websocket:
        websocket.send_json({
            "prompt": "Move the red box next to the blue box. Do not move the glass.",
            "algorithm": "A*",
            "enumerate_graph": True,
            "max_nodes": 50,
            "max_edges": 150,
            "provider_type": "mock",
            "step_delay": 0.0,
        })

        stages_received = []
        streamed_nodes = []
        streamed_edges = []
        graph_stats = None

        while True:
            data = websocket.receive_json()
            stage = data["stage"]
            stages_received.append(stage)

            if stage == "GRAPH_NODE_BATCH":
                streamed_nodes.extend(data["data"]["nodes"])
            elif stage == "GRAPH_EDGE_BATCH":
                streamed_edges.extend(data["data"]["edges"])
            elif stage in ("GRAPH_ENUMERATION_COMPLETED", "GRAPH_ENUMERATION_TRUNCATED"):
                graph_stats = data["data"]

            if stage in ("PIPELINE_FINISHED", "ERROR"):
                break

        assert "GRAPH_ENUMERATION_STARTED" in stages_received
        assert len(streamed_nodes) > 0
        assert len(streamed_edges) > 0
        assert graph_stats is not None
        # Count reconciliation: total streamed elements match reported stats
        assert len(streamed_nodes) == graph_stats["stats"]["total_nodes"]
        assert len(streamed_edges) == graph_stats["stats"]["total_edges"]
        assert "PIPELINE_FINISHED" in stages_received


def test_websocket_streaming_clarification_required():
    app = create_app()
    client = TestClient(app)
    with client.websocket_connect("/ws/pipeline") as websocket:
        websocket.send_json({
            "prompt": "Deliver the package.",
            "step_delay": 0.0,
        })

        stages_received = []
        messages = []
        while True:
            data = websocket.receive_json()
            stages_received.append(data["stage"])
            messages.append(data.get("message", ""))
            if data["stage"] in ("CLARIFICATION_REQUIRED", "PIPELINE_FINISHED", "ERROR"):
                break

        assert "CLARIFICATION_REQUIRED" in stages_received
        assert any("package" in m.lower() or "where" in m.lower() for m in messages)


def test_websocket_streaming_unsupported_task():
    app = create_app()
    client = TestClient(app)
    with client.websocket_connect("/ws/pipeline") as websocket:
        websocket.send_json({
            "prompt": "Book a flight ticket from Paris to London.",
            "step_delay": 0.0,
        })

        stages_received = []
        while True:
            data = websocket.receive_json()
            stages_received.append(data["stage"])
            if data["stage"] in ("TASK_UNSUPPORTED", "PIPELINE_FINISHED", "ERROR"):
                break

        assert "TASK_UNSUPPORTED" in stages_received


def test_websocket_multi_domain_streaming():
    app = create_app()
    client = TestClient(app)
    with client.websocket_connect("/ws/pipeline") as websocket:
        websocket.send_json({
            "prompt": "Move SKU_A from shelf_1 to dispatch dock.",
            "domain_id": "warehouse",
            "algorithm": "A*",
            "provider_type": "mock",
            "enumerate_graph": False,
            "step_delay": 0.0,
        })

        stages_received = []
        while True:
            data = websocket.receive_json()
            stages_received.append(data["stage"])
            if data["stage"] in ("PIPELINE_FINISHED", "ERROR"):
                break

        assert "PIPELINE_STARTED" in stages_received
        assert "INTERPRETATION_COMPLETED" in stages_received
        assert "SEARCH_COMPLETED" in stages_received
        assert "FINAL_VERIFICATION" in stages_received
        assert "PIPELINE_FINISHED" in stages_received
