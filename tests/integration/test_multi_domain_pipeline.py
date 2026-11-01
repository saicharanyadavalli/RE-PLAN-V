"""Integration tests for Multi-Domain Pipeline and REST API routes."""

import pytest
from fastapi.testclient import TestClient
from app.main import create_app


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


def test_api_domains_endpoint(client: TestClient):
    resp = client.get("/api/domains")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 6
    domain_ids = [d["domain_id"] for d in data]
    assert "blocks_world" in domain_ids
    assert "grid_world" in domain_ids
    assert "household_robotics" in domain_ids
    assert "warehouse" in domain_ids
    assert "scheduling" in domain_ids
    assert "software_workflow" in domain_ids


def test_api_graph_enumerate_endpoint(client: TestClient):
    resp = client.post(
        "/api/graph/enumerate",
        json={
            "domain_id": "blocks_world",
            "prompt": "Stack the red box on the blue box.",
            "max_nodes": 50,
            "max_edges": 100,
            "timeout_seconds": 3.0,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "graph_id" in data
    assert "stats" in data
    assert "elements" in data
    assert data["stats"]["total_nodes"] > 0
    assert data["stats"]["total_edges"] > 0


def test_api_graph_enumerate_explicit_domain_grid_world(client: TestClient):
    resp = client.post(
        "/api/graph/enumerate",
        json={
            "domain_id": "grid_world",
            "prompt": "Move agent from loc_0_0 to loc_1_1.",
            "max_nodes": 50,
            "max_edges": 100,
            "timeout_seconds": 3.0,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["stats"]["total_nodes"] >= 2
    assert data["stats"]["total_edges"] >= 1


def test_api_graph_enumerate_unsupported_task(client: TestClient):
    resp = client.post(
        "/api/graph/enumerate",
        json={
            "domain_id": "auto",
            "prompt": "Book a flight ticket to Paris and buy stocks.",
            "max_nodes": 50,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "UNSUPPORTED"
    assert "unsupported" in data["explanation"].lower()


def test_api_system_info_lists_all_domains(client: TestClient):
    resp = client.get("/api/system/info")
    assert resp.status_code == 200
    data = resp.json()
    assert "graph_mode" in data
    assert len(data["domains"]) >= 6
