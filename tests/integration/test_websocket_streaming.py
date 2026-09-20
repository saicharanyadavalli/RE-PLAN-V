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
