"""Stage 11 Integration Tests: Hard Resource Ceilings, Type Boundaries, and Bounded Concurrency."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from core.graph.resource_limits import GraphBudgetLimits, graph_concurrency_manager


@pytest.fixture
def client():
    return TestClient(create_app())


def test_reject_max_nodes_exceeding_ceiling(client: TestClient):
    """Verify max_nodes > 5000 is rejected with HTTP 422."""
    resp = client.post(
        "/api/graph/enumerate",
        json={"domain_id": "blocks_world", "max_nodes": 5001},
    )
    assert resp.status_code == 422


def test_reject_max_edges_exceeding_ceiling(client: TestClient):
    """Verify max_edges > 20000 is rejected with HTTP 422."""
    resp = client.post(
        "/api/graph/enumerate",
        json={"domain_id": "blocks_world", "max_edges": 20001},
    )
    assert resp.status_code == 422


def test_reject_timeout_exceeding_ceiling(client: TestClient):
    """Verify timeout_seconds > 30.0 is rejected with HTTP 422."""
    resp = client.post(
        "/api/graph/enumerate",
        json={"domain_id": "blocks_world", "timeout_seconds": 30.5},
    )
    assert resp.status_code == 422


def test_reject_boolean_resource_limits(client: TestClient):
    """Verify boolean values for max_nodes, max_edges, and timeout_seconds are strictly rejected."""
    r1 = client.post("/api/graph/enumerate", json={"max_nodes": True})
    assert r1.status_code == 422

    r2 = client.post("/api/graph/enumerate", json={"max_edges": False})
    assert r2.status_code == 422

    r3 = client.post("/api/graph/enumerate", json={"timeout_seconds": True})
    assert r3.status_code == 422


def test_reject_nan_and_inf_timeout(client: TestClient):
    """Verify NaN and Inf are rejected as timeout values."""
    # JSON standard does not permit raw NaN or Infinity without strings, but string forms should be rejected
    r1 = client.post("/api/graph/enumerate", json={"timeout_seconds": "nan"})
    assert r1.status_code == 422

    r2 = client.post("/api/graph/enumerate", json={"timeout_seconds": "inf"})
    assert r2.status_code == 422


def test_bounded_concurrency_manager_429(client: TestClient):
    """Verify that when 2 slots are occupied, a third request receives HTTP 429."""
    # Manually occupy both slots
    slot1 = graph_concurrency_manager.acquire()
    slot2 = graph_concurrency_manager.acquire()
    assert slot1 is True
    assert slot2 is True

    try:
        # A 3rd request must be rejected with 429
        resp = client.post(
            "/api/graph/enumerate",
            json={"domain_id": "blocks_world", "max_nodes": 10},
        )
        assert resp.status_code == 429
        assert "capacity exceeded" in resp.json()["detail"]
    finally:
        # Release both acquired slots
        graph_concurrency_manager.release()
        graph_concurrency_manager.release()

    # Now a request should succeed
    resp_after = client.post(
        "/api/graph/enumerate",
        json={"domain_id": "blocks_world", "max_nodes": 10},
    )
    assert resp_after.status_code == 200
